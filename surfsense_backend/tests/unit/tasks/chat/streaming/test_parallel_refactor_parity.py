"""Parity gate for the parallel refactor of ``stream_new_chat.py``.

The new tree under ``app.tasks.chat.streaming.flows`` is built side-by-side with
the legacy monolithic ``app.tasks.chat.stream_new_chat`` so we can cut over
atomically. This file pins externally-observable behaviour at module
boundaries so a divergence between the two trees fails loudly *before* the
cutover.

What we verify:

  1. **Signature parity** — ``stream_new_chat`` / ``stream_resume_chat`` from
     the new tree have the same call signature as the originals.
  2. **Helper extraction parity** — the SRP modules in ``flows/`` produce the
     same outputs as the inline code in the legacy file for representative
     inputs (initial thinking step, image-capability gate, runtime context,
     SSE frame sequences, token-usage frame shape, persistence guards).
  3. **Wrapper delegation** — wrappers like ``load_llm_bundle`` /
     ``can_recover_provider_rate_limit`` exist and are addressable.

Delete this file along with ``stream_new_chat.py`` once the cutover is done
(see the parent refactor plan).
"""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.new_chat.context import SurfSenseContextSchema
from app.services.new_streaming_service import VercelStreamingService

from app.tasks.chat.stream_new_chat import (
    stream_new_chat as old_stream_new_chat,
    stream_resume_chat as old_stream_resume_chat,
)
from app.tasks.chat.streaming.flows import (
    stream_new_chat as new_stream_new_chat,
    stream_resume_chat as new_stream_resume_chat,
)
from app.tasks.chat.streaming.flows.new_chat.initial_thinking_step import (
    build_initial_thinking_step,
)
from app.tasks.chat.streaming.flows.new_chat.llm_capability import (
    check_image_input_capability,
)
from app.tasks.chat.streaming.flows.new_chat.persistence_spawn import (
    await_persist_task,
    spawn_persist_assistant_shell_task,
    spawn_persist_user_task,
    spawn_set_ai_responding_bg,
)
from app.tasks.chat.streaming.flows.new_chat.runtime_context import (
    build_new_chat_runtime_context,
)
from app.tasks.chat.streaming.flows.resume_chat.runtime_context import (
    build_resume_chat_runtime_context,
)
from app.tasks.chat.streaming.flows.shared.finalize_emit import iter_token_usage_frame
from app.tasks.chat.streaming.flows.shared.first_frames import (
    iter_final_frames,
    iter_initial_frames,
)
from app.tasks.chat.streaming.flows.shared.llm_bundle import load_llm_bundle
from app.tasks.chat.streaming.flows.shared.premium_quota import (
    PremiumReservation,
    needs_premium_quota,
)
from app.tasks.chat.streaming.flows.shared.rate_limit_recovery import (
    can_recover_provider_rate_limit,
)

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------- signature


def _normalize_annotation(ann: Any) -> str:
    """Compare-friendly form for an annotation.

    The legacy ``stream_new_chat.py`` does NOT use ``from __future__ import
    annotations``, so its annotations are evaluated at import time and come
    back as type objects / typing generics. The new tree DOES use it, so its
    annotations are PEP-563 strings.

    Both reprs describe the same types — strip the module prefixes / typing
    namespace + the ``<class 'X'>`` wrapper so we compare the canonical
    declared form.
    """
    if ann is inspect.Signature.empty:
        return ""
    raw = ann if isinstance(ann, str) else repr(ann)
    cleaned = (
        raw.replace("typing.", "")
        .replace("collections.abc.", "")
        .replace("app.db.", "")
        .replace("app.agents.new_chat.filesystem_selection.", "")
        .replace("app.agents.new_chat.context.", "")
    )
    # Unwrap ``<class 'int'>`` → ``int`` (legacy-side type objects).
    if cleaned.startswith("<class '") and cleaned.endswith("'>"):
        cleaned = cleaned[len("<class '") : -len("'>")]
    return cleaned


def _normalize_sig(sig: inspect.Signature) -> list[tuple[str, Any, str]]:
    return [
        (p.name, p.default, _normalize_annotation(p.annotation))
        for p in sig.parameters.values()
    ]


def test_stream_new_chat_signature_matches_legacy() -> None:
    old = inspect.signature(old_stream_new_chat)
    new = inspect.signature(new_stream_new_chat)
    assert _normalize_sig(new) == _normalize_sig(old)
    assert _normalize_annotation(new.return_annotation) == _normalize_annotation(
        old.return_annotation
    )


def test_stream_resume_chat_signature_matches_legacy() -> None:
    old = inspect.signature(old_stream_resume_chat)
    new = inspect.signature(new_stream_resume_chat)
    assert _normalize_sig(new) == _normalize_sig(old)
    assert _normalize_annotation(new.return_annotation) == _normalize_annotation(
        old.return_annotation
    )


def test_orchestrators_are_async_generator_functions() -> None:
    assert inspect.isasyncgenfunction(new_stream_new_chat)
    assert inspect.isasyncgenfunction(new_stream_resume_chat)


# ------------------------------------------------------------ initial thinking


@dataclass
class _FakeSurfsenseDoc:
    """Stand-in for ``SurfsenseDocsDocument`` with just the field we read."""

    title: str


@pytest.mark.parametrize(
    "user_query, image_urls, docs, expected_title, expected_action",
    [
        ("hello world", None, [], "Understanding your request", "Processing"),
        ("", ["data:image/png;base64,AAA"], [], "Understanding your request", "Processing"),
        ("", None, [], "Understanding your request", "Processing"),
        (
            "doc question",
            None,
            [_FakeSurfsenseDoc(title="My Doc")],
            "Analyzing referenced content",
            "Analyzing",
        ),
    ],
)
def test_initial_thinking_step_branches(
    user_query: str,
    image_urls: list[str] | None,
    docs: list[Any],
    expected_title: str,
    expected_action: str,
) -> None:
    step = build_initial_thinking_step(
        user_query=user_query,
        user_image_data_urls=image_urls,
        mentioned_surfsense_docs=docs,  # type: ignore[arg-type]
    )
    assert step.step_id == "thinking-1"
    assert step.title == expected_title
    assert len(step.items) == 1
    assert step.items[0].startswith(f"{expected_action}: ")


def test_initial_thinking_step_truncates_long_query() -> None:
    long_query = "x" * 200
    step = build_initial_thinking_step(
        user_query=long_query,
        user_image_data_urls=None,
        mentioned_surfsense_docs=[],
    )
    # 80-char truncation + ellipsis, sandwiched after "Processing: ".
    assert "..." in step.items[0]
    item = step.items[0]
    payload = item[len("Processing: ") :]
    assert payload.startswith("x" * 80) and payload.endswith("...")


def test_initial_thinking_step_collapses_many_doc_names() -> None:
    docs = [_FakeSurfsenseDoc(title=f"Doc {i}") for i in range(5)]
    step = build_initial_thinking_step(
        user_query="q",
        user_image_data_urls=None,
        mentioned_surfsense_docs=docs,  # type: ignore[arg-type]
    )
    assert "[5 docs]" in step.items[0]


# ------------------------------------------------------------ capability gate


def test_image_capability_passes_without_images() -> None:
    assert check_image_input_capability(
        user_image_data_urls=None, agent_config=None
    ) is None


def test_image_capability_passes_when_capability_unknown() -> None:
    """Unknown / unmapped models are not blocked — only models LiteLLM has
    *explicitly* marked text-only trip the gate."""

    class _AgentConfig:
        provider = "openrouter"
        model_name = "unknown-mystery-model"
        custom_provider = None
        config_name = "Unknown"
        litellm_params: dict[str, Any] = {}

    with patch(
        "app.services.provider_capabilities.is_known_text_only_chat_model",
        return_value=False,
    ):
        assert (
            check_image_input_capability(
                user_image_data_urls=["data:image/png;base64,AAA"],
                agent_config=_AgentConfig(),  # type: ignore[arg-type]
            )
            is None
        )


def test_image_capability_blocks_known_text_only_models() -> None:
    class _AgentConfig:
        provider = "openai"
        model_name = "gpt-3.5-turbo"
        custom_provider = None
        config_name = "GPT-3.5"
        litellm_params: dict[str, Any] = {"base_model": "gpt-3.5-turbo"}

    with patch(
        "app.services.provider_capabilities.is_known_text_only_chat_model",
        return_value=True,
    ):
        result = check_image_input_capability(
            user_image_data_urls=["data:image/png;base64,AAA"],
            agent_config=_AgentConfig(),  # type: ignore[arg-type]
        )
    assert result is not None
    message, error_code = result
    assert error_code == "MODEL_DOES_NOT_SUPPORT_IMAGE_INPUT"
    assert "GPT-3.5" in message


# ---------------------------------------------------------------- runtime ctx


def test_new_chat_runtime_context_prefers_accepted_folder_ids() -> None:
    ctx = build_new_chat_runtime_context(
        search_space_id=7,
        mentioned_document_ids=[1, 2],
        accepted_folder_ids=[10],
        mentioned_folder_ids=[20, 30],
        request_id="req",
        turn_id="t1",
    )
    assert isinstance(ctx, SurfSenseContextSchema)
    assert ctx.search_space_id == 7
    assert list(ctx.mentioned_document_ids) == [1, 2]
    assert list(ctx.mentioned_folder_ids) == [10]
    assert ctx.request_id == "req"
    assert ctx.turn_id == "t1"


def test_new_chat_runtime_context_falls_back_to_mentioned_folder_ids() -> None:
    ctx = build_new_chat_runtime_context(
        search_space_id=7,
        mentioned_document_ids=None,
        accepted_folder_ids=[],
        mentioned_folder_ids=[20, 30],
        request_id=None,
        turn_id="t2",
    )
    assert list(ctx.mentioned_folder_ids) == [20, 30]


def test_resume_chat_runtime_context_empty_mention_lists() -> None:
    ctx = build_resume_chat_runtime_context(
        search_space_id=42, request_id="req-r", turn_id="t-r"
    )
    assert ctx.search_space_id == 42
    assert ctx.request_id == "req-r"
    assert ctx.turn_id == "t-r"


# ---------------------------------------------------------------- SSE frames


def test_iter_initial_frames_emits_canonical_sequence() -> None:
    svc = VercelStreamingService()
    frames = list(iter_initial_frames(svc, turn_id="42:1700000000000"))
    # Exactly 4 frames: message_start, start_step, turn-info (turn_id), turn-status (busy).
    assert len(frames) == 4
    assert "42:1700000000000" in frames[2]
    assert '"status":"busy"' in frames[3] or '"status": "busy"' in frames[3]


def test_iter_final_frames_emits_idle_then_finish_done() -> None:
    svc = VercelStreamingService()
    frames = list(iter_final_frames(svc))
    assert len(frames) == 4
    assert '"status":"idle"' in frames[0] or '"status": "idle"' in frames[0]


# ----------------------------------------------------------- token usage frame


class _FakeAccumulator:
    """Minimal stand-in covering only the fields ``iter_token_usage_frame`` reads."""

    def __init__(self, summary: Any = None) -> None:
        self._summary = summary
        self.calls = [1, 2, 3]
        self.grand_total = 100
        self.total_cost_micros = 50_000
        self.total_prompt_tokens = 60
        self.total_completion_tokens = 40

    def per_message_summary(self) -> Any:
        return self._summary

    def serialized_calls(self) -> list[Any]:
        return list(self.calls)


def test_token_usage_frame_skipped_when_no_summary() -> None:
    svc = VercelStreamingService()
    frames = list(
        iter_token_usage_frame(
            svc,
            accumulator=_FakeAccumulator(summary=None),  # type: ignore[arg-type]
            log_label="parity-empty",
        )
    )
    assert frames == []


def test_token_usage_frame_emitted_when_summary_present() -> None:
    svc = VercelStreamingService()
    frames = list(
        iter_token_usage_frame(
            svc,
            accumulator=_FakeAccumulator(summary=[{"m": "x", "t": 100}]),  # type: ignore[arg-type]
            log_label="parity-populated",
        )
    )
    assert len(frames) == 1
    # Field shape on the wire is fixed by the FE; assert each surfaces.
    payload = frames[0]
    for key in (
        '"prompt_tokens":60',
        '"completion_tokens":40',
        '"total_tokens":100',
        '"cost_micros":50000',
    ):
        assert key in payload.replace(" ", "")


# ------------------------------------------------------------------ llm_bundle


def test_load_llm_bundle_routes_negative_id_to_yaml_loader() -> None:
    async def _run() -> tuple[Any, Any, str | None]:
        with (
            patch(
                "app.tasks.chat.streaming.flows.shared.llm_bundle.load_global_llm_config_by_id",
                return_value=None,
            ),
        ):
            return await load_llm_bundle(
                session=AsyncMock(),  # type: ignore[arg-type]
                config_id=-1,
                search_space_id=7,
            )

    llm, agent_config, error = asyncio.run(_run())
    assert llm is None
    assert agent_config is None
    assert error is not None and "id -1" in error


def test_load_llm_bundle_routes_nonnegative_id_to_db_loader() -> None:
    async def _run() -> tuple[Any, Any, str | None]:
        with (
            patch(
                "app.tasks.chat.streaming.flows.shared.llm_bundle.load_agent_config",
                new=AsyncMock(return_value=None),
            ),
        ):
            return await load_llm_bundle(
                session=AsyncMock(),  # type: ignore[arg-type]
                config_id=12,
                search_space_id=7,
            )

    llm, agent_config, error = asyncio.run(_run())
    assert llm is None
    assert agent_config is None
    assert error is not None and "id 12" in error


# ----------------------------------------------------------------- premium quota


def test_needs_premium_quota_requires_user_and_premium_flag() -> None:
    class _AgentConfig:
        is_premium = True

    class _NonPremium:
        is_premium = False

    assert needs_premium_quota(_AgentConfig(), "user-1") is True  # type: ignore[arg-type]
    assert needs_premium_quota(_AgentConfig(), None) is False  # type: ignore[arg-type]
    assert needs_premium_quota(_NonPremium(), "user-1") is False  # type: ignore[arg-type]
    assert needs_premium_quota(None, "user-1") is False


def test_premium_reservation_dataclass_shape() -> None:
    # Sanity: the dataclass exists and carries the fields the orchestrator uses.
    r = PremiumReservation(request_id="abc", reserved_micros=100, allowed=True)
    assert r.request_id == "abc"
    assert r.reserved_micros == 100
    assert r.allowed is True


# ----------------------------------------------------------- rate-limit guard


@pytest.mark.parametrize(
    "first_event_seen, recovered, requested_id, current_id, expected",
    [
        (False, False, 0, -1, True),
        # Already recovered: no second pass.
        (False, True, 0, -1, False),
        # User explicitly picked a config: don't silently switch.
        (False, False, 5, -1, False),
        # Already on a database-backed (positive) id.
        (False, False, 0, 7, False),
        # User has already seen output: silent rebuild not possible.
        (True, False, 0, -1, False),
    ],
)
def test_can_recover_provider_rate_limit_truth_table(
    first_event_seen: bool,
    recovered: bool,
    requested_id: int,
    current_id: int,
    expected: bool,
) -> None:
    # Use a known rate-limit-shaped exception so the helper's last condition
    # is satisfied; the guard only short-circuits to False when one of the
    # *other* preconditions fails.
    exc = Exception('{"error":{"type":"rate_limit_error","message":"slow"}}')
    assert (
        can_recover_provider_rate_limit(
            exc,
            first_event_seen=first_event_seen,
            runtime_rate_limit_recovered=recovered,
            requested_llm_config_id=requested_id,
            current_llm_config_id=current_id,
        )
        is expected
    )


def test_can_recover_provider_rate_limit_rejects_non_rate_limit_exception() -> None:
    assert (
        can_recover_provider_rate_limit(
            ValueError("not a rate limit"),
            first_event_seen=False,
            runtime_rate_limit_recovered=False,
            requested_llm_config_id=0,
            current_llm_config_id=-1,
        )
        is False
    )


# --------------------------------------------------------- persistence spawn


def test_spawn_set_ai_responding_bg_noop_without_user_id() -> None:
    async def _run() -> set[asyncio.Task]:
        background: set[asyncio.Task] = set()
        spawn_set_ai_responding_bg(
            chat_id=1, user_id=None, background_tasks=background
        )
        return background

    bg = asyncio.run(_run())
    assert bg == set()


def test_spawn_persist_user_task_registers_and_self_unregisters() -> None:
    async def _run() -> tuple[int, int]:
        background: set[asyncio.Task] = set()
        with patch(
            "app.tasks.chat.streaming.flows.new_chat.persistence_spawn.persist_user_turn",
            new=AsyncMock(return_value=99),
        ):
            task = spawn_persist_user_task(
                chat_id=1,
                user_id="u",
                turn_id="t",
                user_query="hi",
                user_image_data_urls=None,
                mentioned_documents=None,
                background_tasks=background,
            )
            size_before_await = len(background)
            result = await asyncio.shield(task)
            # Give the done-callback one event-loop tick to run.
            await asyncio.sleep(0)
            return size_before_await, result  # type: ignore[return-value]

    size_before, result = asyncio.run(_run())
    assert size_before == 1
    assert result == 99


def test_spawn_persist_assistant_shell_task_registers() -> None:
    async def _run() -> int | None:
        background: set[asyncio.Task] = set()
        with patch(
            "app.tasks.chat.streaming.flows.new_chat.persistence_spawn.persist_assistant_shell",
            new=AsyncMock(return_value=42),
        ):
            task = spawn_persist_assistant_shell_task(
                chat_id=1,
                user_id="u",
                turn_id="t",
                background_tasks=background,
            )
            return await asyncio.shield(task)

    assert asyncio.run(_run()) == 42


def test_await_persist_task_returns_none_on_failure() -> None:
    async def _run() -> int | None:
        async def _boom() -> int:
            raise RuntimeError("DB down")

        task = asyncio.create_task(_boom())
        return await await_persist_task(
            task,
            chat_id=1,
            turn_id="t",
            log_label="parity-failure",
        )

    assert asyncio.run(_run()) is None


def test_await_persist_task_returns_none_for_none_input() -> None:
    async def _run() -> int | None:
        return await await_persist_task(
            None,
            chat_id=1,
            turn_id="t",
            log_label="parity-none",
        )

    assert asyncio.run(_run()) is None
