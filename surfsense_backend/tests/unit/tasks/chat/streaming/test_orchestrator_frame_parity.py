"""Byte-for-byte frame parity: legacy monolith vs refactored flows orchestrators.

The agent-content portion of the stream (`text-*`, tool cards, thinking-step
updates) flows through **shared** code in both implementations
(`stream_output` -> `EventRelay.relay` -> handlers), so it cannot diverge. The
only independently-written part is the *orchestrator glue*: the initial frames,
persistence-handshake frames, error/terminal branches, and final frames.

This module drives BOTH ``stream_new_chat`` implementations (legacy
``app.tasks.chat.stream_new_chat`` and the refactored
``app.tasks.chat.streaming.flows``) through the deterministic glue paths and
asserts the emitted SSE frame sequences are **byte-for-byte identical**. These
are the paths where divergence could hide; the agent-streaming portion is shared
and is covered separately.

Determinism is enforced by:
  * freezing ``time.time`` (so ``turn_id = f"{chat_id}:{ms}"`` is stable),
  * a deterministic ``uuid`` sequence for the streaming-service id generators,
  * stubbing every DB/LLM/agent seam (LLM resolution, persistence, connector,
    checkpointer, session) to fixed values.

Cutover gate: when these are green, the live callers can be flipped to the
flows orchestrators.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.services.new_streaming_service as _nss
from app.tasks.chat.stream_new_chat import (
    stream_new_chat as old_stream_new_chat,
    stream_resume_chat as old_stream_resume_chat,
)
from app.tasks.chat.streaming.flows import (
    stream_new_chat as new_stream_new_chat,
    stream_resume_chat as new_stream_resume_chat,
)

pytestmark = pytest.mark.unit

_FIXED_EPOCH = 1_700_000_000.0  # -> turn_id "<chat_id>:1700000000000"


# --------------------------------------------------------------------------- #
# Deterministic uuid for the streaming-service id generators
# --------------------------------------------------------------------------- #


class _SeqUUID:
    """Drop-in for the ``uuid`` module used by ``new_streaming_service``.

    Only ``uuid4().hex`` is consumed by the id generators. We hand out a
    monotonic, zero-padded hex so two runs that emit the same number of ids in
    the same order produce identical bytes.
    """

    def __init__(self) -> None:
        self._n = 0

    def reset(self) -> None:
        self._n = 0

    def uuid4(self) -> SimpleNamespace:
        self._n += 1
        return SimpleNamespace(hex=f"{self._n:032x}")


_SEQ = _SeqUUID()


# --------------------------------------------------------------------------- #
# Fake session: the orchestrator owns ``async_session_maker()``; for the glue
# paths every real consumer is stubbed, so a no-op session suffices.
# --------------------------------------------------------------------------- #


class _FakeResult:
    """Empty-everything SQLAlchemy ``Result`` stand-in for pre-stream reads."""

    def scalars(self) -> "_FakeResult":
        return self

    def first(self) -> None:
        return None

    def all(self) -> list[Any]:
        return []

    def one_or_none(self) -> None:
        return None

    def scalar_one_or_none(self) -> None:
        return None

    def scalar(self) -> None:
        return None

    def fetchall(self) -> list[Any]:
        return []

    def __iter__(self):
        return iter(())


class _FakeSession:
    async def commit(self) -> None:  # pragma: no cover - trivial
        return None

    async def rollback(self) -> None:  # pragma: no cover - trivial
        return None

    async def close(self) -> None:  # pragma: no cover - trivial
        return None

    def expunge_all(self) -> None:  # pragma: no cover - trivial
        return None

    def add(self, *a: Any, **k: Any) -> None:  # pragma: no cover - trivial
        return None

    async def flush(self, *a: Any, **k: Any) -> None:  # pragma: no cover
        return None

    async def execute(self, *a: Any, **k: Any) -> _FakeResult:
        return _FakeResult()


class _FakeConnectorService:
    def __init__(self, *a: Any, **k: Any) -> None:
        pass

    async def get_connector_by_type(self, *a: Any, **k: Any) -> None:
        return None


def _patch(monkeypatch: pytest.MonkeyPatch, target: str, value: Any) -> None:
    """``setattr`` that tolerates a missing attr (binding may be local-import)."""
    monkeypatch.setattr(target, value, raising=False)


def _apply_common(
    monkeypatch: pytest.MonkeyPatch,
    *,
    pin_raises: ValueError | None = None,
    resolved_id: int = -1,
    llm_load_ok: bool = True,
    persist_user_id: int | None = 101,
    persist_assistant_id: int | None = 102,
) -> None:
    """Patch every glue seam in BOTH implementations to deterministic values."""
    # Time -> stable turn_id and any retry_after_at.
    monkeypatch.setattr("time.time", lambda: _FIXED_EPOCH)

    # Deterministic streaming-service ids.
    monkeypatch.setattr(_nss, "uuid", _SEQ)

    fake_model = MagicMock(name="scripted_llm")

    # --- session ---
    for tgt in (
        "app.tasks.chat.stream_new_chat.async_session_maker",
        "app.tasks.chat.streaming.flows.new_chat.orchestrator.async_session_maker",
        "app.tasks.chat.streaming.flows.resume_chat.orchestrator.async_session_maker",
    ):
        _patch(monkeypatch, tgt, _FakeSession)

    # --- connector service ---
    for tgt in (
        "app.tasks.chat.stream_new_chat.ConnectorService",
        "app.tasks.chat.streaming.flows.shared.pre_stream_setup.ConnectorService",
    ):
        _patch(monkeypatch, tgt, _FakeConnectorService)

    # --- checkpointer ---
    for tgt in (
        "app.tasks.chat.stream_new_chat.get_checkpointer",
        "app.tasks.chat.streaming.flows.shared.pre_stream_setup.get_checkpointer",
    ):
        _patch(monkeypatch, tgt, AsyncMock(return_value=MagicMock(name="checkpointer")))

    # --- agent factory (built but never streamed on glue paths) ---
    # Resume routing awaits ``agent.aget_state`` before persist, so the fake
    # agent exposes async state accessors returning an empty (no-interrupt)
    # snapshot. ``astream_events`` is never reached on glue paths.
    fake_agent = MagicMock(name="agent")
    fake_agent.aget_state = AsyncMock(
        return_value=SimpleNamespace(values={}, tasks=[], interrupts=[], next=())
    )
    fake_agent.aupdate_state = AsyncMock(return_value=None)
    agent_factory = AsyncMock(return_value=fake_agent)
    for tgt in (
        "app.tasks.chat.stream_new_chat.create_multi_agent_chat_deep_agent",
        "app.tasks.chat.streaming.flows.new_chat.orchestrator.create_multi_agent_chat_deep_agent",
        "app.tasks.chat.streaming.flows.resume_chat.orchestrator.create_multi_agent_chat_deep_agent",
    ):
        _patch(monkeypatch, tgt, agent_factory)

    # --- LLM resolution (auto-pin) ---
    if pin_raises is not None:
        async def _resolver(*a: Any, **k: Any):
            raise pin_raises
    else:
        async def _resolver(*a: Any, **k: Any):
            return SimpleNamespace(resolved_llm_config_id=resolved_id)

    _patch(monkeypatch, "app.services.auto_model_pin_service.resolve_or_get_pinned_llm_config_id", _resolver)
    _patch(monkeypatch, "app.tasks.chat.stream_new_chat.resolve_or_get_pinned_llm_config_id", _resolver)
    _patch(
        monkeypatch,
        "app.tasks.chat.streaming.flows.new_chat.auto_pin.resolve_or_get_pinned_llm_config_id",
        _resolver,
    )

    # --- LLM bundle ---
    sentinel_cfg = object() if llm_load_ok else None
    _patch(monkeypatch, "app.tasks.chat.stream_new_chat.load_global_llm_config_by_id", lambda cid: sentinel_cfg)
    _patch(
        monkeypatch,
        "app.tasks.chat.streaming.flows.shared.llm_bundle.load_global_llm_config_by_id",
        lambda cid: sentinel_cfg,
    )
    _patch(monkeypatch, "app.tasks.chat.stream_new_chat.create_chat_litellm_from_config", lambda cfg: fake_model)
    _patch(
        monkeypatch,
        "app.tasks.chat.streaming.flows.shared.llm_bundle.create_chat_litellm_from_config",
        lambda cfg: fake_model,
    )
    # agent_config := None keeps premium + capability gates inert and identical.
    from app.agents.shared.llm_config import AgentConfig

    monkeypatch.setattr(AgentConfig, "from_yaml_config", staticmethod(lambda cfg: None))

    # --- persistence ---
    async def _persist_user(*a: Any, **k: Any):
        return persist_user_id

    async def _persist_assistant(*a: Any, **k: Any):
        return persist_assistant_id

    async def _finalize(*a: Any, **k: Any):
        return None

    for mod in (
        "app.tasks.chat.persistence",
        "app.tasks.chat.streaming.flows.new_chat.persistence_spawn",
    ):
        _patch(monkeypatch, f"{mod}.persist_user_turn", _persist_user)
        _patch(monkeypatch, f"{mod}.persist_assistant_shell", _persist_assistant)
    # Resume binds ``persist_assistant_shell`` in its own assistant_shell module.
    _patch(
        monkeypatch,
        "app.tasks.chat.streaming.flows.resume_chat.assistant_shell.persist_assistant_shell",
        _persist_assistant,
    )
    _patch(monkeypatch, "app.tasks.chat.persistence.finalize_assistant_turn", _finalize)

    # --- collaboration flags ---
    async def _noop(*a: Any, **k: Any):
        return None

    for tgt in (
        "app.tasks.chat.stream_new_chat.set_ai_responding",
        "app.tasks.chat.stream_new_chat.clear_ai_responding",
        "app.tasks.chat.streaming.flows.new_chat.persistence_spawn.set_ai_responding",
        "app.services.chat_session_state_service.set_ai_responding",
        "app.services.chat_session_state_service.clear_ai_responding",
    ):
        _patch(monkeypatch, tgt, _noop)


async def _collect(genfunc: Any, **kwargs: Any) -> list[str]:
    frames: list[str] = []
    async for frame in genfunc(**kwargs):
        frames.append(frame)
    return frames


async def _run_both(kwargs: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Drive both NEW-chat implementations on identical inputs."""
    _SEQ.reset()
    old = await _collect(old_stream_new_chat, **kwargs)
    _SEQ.reset()
    new = await _collect(new_stream_new_chat, **kwargs)
    return old, new


async def _run_both_resume(kwargs: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Drive both RESUME-chat implementations on identical inputs."""
    _SEQ.reset()
    old = await _collect(old_stream_resume_chat, **kwargs)
    _SEQ.reset()
    new = await _collect(new_stream_resume_chat, **kwargs)
    return old, new


def _assert_parity(old: list[str], new: list[str]) -> None:
    """Byte-for-byte equality with a readable first-divergence message."""
    for i, (a, b) in enumerate(zip(old, new, strict=False)):
        assert a == b, f"frame[{i}] differs:\n  old={a!r}\n  new={b!r}"
    assert len(old) == len(new), (
        f"frame count differs: old={len(old)} new={len(new)}\n"
        f"  old tail={old[len(new):]!r}\n  new tail={new[len(old):]!r}"
    )
    assert old[-1].strip() == "data: [DONE]"


# --------------------------------------------------------------------------- #
# NEW-chat scenarios
# --------------------------------------------------------------------------- #

_NEW_KW = dict(user_query="hi", search_space_id=1, chat_id=42, user_id=None)


@pytest.mark.asyncio
async def test_auto_pin_failure_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    """Auto-pin raises -> identical ``[error, DONE]`` from both."""
    _apply_common(monkeypatch, pin_raises=ValueError("no eligible config"))
    old, new = await _run_both(dict(_NEW_KW))
    _assert_parity(old, new)
    assert len(old) == 2
    assert '"errorCode": "SERVER_ERROR"' in old[0]


@pytest.mark.asyncio
async def test_llm_load_failure_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM bundle load fails -> identical ``[error, DONE]`` from both."""
    _apply_common(monkeypatch, llm_load_ok=False)
    old, new = await _run_both(dict(_NEW_KW))
    _assert_parity(old, new)
    assert len(old) == 2
    assert '"errorCode": "SERVER_ERROR"' in old[0]


@pytest.mark.asyncio
async def test_persist_user_failure_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    """User-turn persist returns None.

    Exercises the full initial-frame ordering (start, start-step, turn-info,
    turn-status busy), the MESSAGE_PERSIST_FAILED error, and final frames.
    """
    _apply_common(monkeypatch, persist_user_id=None)
    old, new = await _run_both(dict(_NEW_KW))
    _assert_parity(old, new)
    assert '"type": "start"' in old[0]
    assert '"chat_turn_id": "42:1700000000000"' in old[2]
    assert any('"errorCode": "MESSAGE_PERSIST_FAILED"' in f for f in old)
    assert any('"type": "finish"' in f for f in old)


@pytest.mark.asyncio
async def test_persist_assistant_failure_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    """Assistant-shell persist returns None.

    Adds the ``data-user-message-id`` handshake frame ahead of the error.
    """
    _apply_common(monkeypatch, persist_user_id=101, persist_assistant_id=None)
    old, new = await _run_both(dict(_NEW_KW))
    _assert_parity(old, new)
    assert any('"data-user-message-id"' in f and '"message_id": 101' in f for f in old)
    assert any('"errorCode": "MESSAGE_PERSIST_FAILED"' in f for f in old)


@pytest.mark.asyncio
async def test_prestream_exception_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    """A pre-stream failure routes both through the top-level ``except`` path.

    Resolver returns a non-int so ``turn_id`` math / downstream use raises after
    the span opens but before initial frames: both must emit the identical
    ``busy -> error -> idle -> finish-step -> finish -> DONE`` terminal sequence.
    """

    async def _bad_resolver(*a: Any, **k: Any):
        raise RuntimeError("boom in pre-stream")

    _apply_common(monkeypatch)
    # Override the resolver with a non-ValueError so the classified early-error
    # branches don't catch it -> top-level except path.
    for tgt in (
        "app.services.auto_model_pin_service.resolve_or_get_pinned_llm_config_id",
        "app.tasks.chat.stream_new_chat.resolve_or_get_pinned_llm_config_id",
        "app.tasks.chat.streaming.flows.new_chat.auto_pin.resolve_or_get_pinned_llm_config_id",
    ):
        _patch(monkeypatch, tgt, _bad_resolver)
    old, new = await _run_both(dict(_NEW_KW))
    _assert_parity(old, new)
    assert any('"type": "error"' in f for f in old)


# --------------------------------------------------------------------------- #
# RESUME-chat scenarios (no title-generation path -> fully deterministic)
# --------------------------------------------------------------------------- #

_RESUME_KW = dict(chat_id=42, search_space_id=1, decisions=[], user_id=None)


async def _collect_resume_old() -> list[str]:
    _SEQ.reset()
    return await _collect(old_stream_resume_chat, **dict(_RESUME_KW))


# NOTE: KNOWN, INTENTIONAL DIVERGENCE (flows fixes a latent monolith bug).
#
# In ``stream_resume_chat`` the monolith defines ``_resume_premium_request_id``
# (line ~2363) AFTER the auto-pin / LLM-load early-return points (~2346 / ~2356).
# Its ``finally`` block (line ~2918) reads that variable, so a resume turn whose
# auto-pin raises or whose LLM bundle fails to load crashes with
# ``UnboundLocalError`` instead of emitting a clean terminal-error frame. The
# refactored flows orchestrator does NOT have this bug — it emits the proper
# ``[error, DONE]`` sequence. We assert the divergence explicitly so the cutover
# is a documented behavior IMPROVEMENT rather than a silent change.


@pytest.mark.asyncio
async def test_resume_auto_pin_failure_flows_fixes_monolith_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _apply_common(monkeypatch, pin_raises=ValueError("no eligible config"))
    # Monolith: latent UnboundLocalError in the finally clause.
    with pytest.raises(UnboundLocalError, match="_resume_premium_request_id"):
        await _collect_resume_old()
    # Flows: clean terminal error.
    _SEQ.reset()
    new = await _collect(new_stream_resume_chat, **dict(_RESUME_KW))
    assert len(new) == 2
    assert new[-1].strip() == "data: [DONE]"
    assert '"type": "error"' in new[0]


@pytest.mark.asyncio
async def test_resume_llm_load_failure_flows_fixes_monolith_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _apply_common(monkeypatch, llm_load_ok=False)
    with pytest.raises(UnboundLocalError, match="_resume_premium_request_id"):
        await _collect_resume_old()
    _SEQ.reset()
    new = await _collect(new_stream_resume_chat, **dict(_RESUME_KW))
    assert len(new) == 2
    assert new[-1].strip() == "data: [DONE]"
    assert '"type": "error"' in new[0]


@pytest.mark.asyncio
async def test_resume_persist_assistant_failure_parity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resume emits NO user-message-id frame; only the assistant handshake path."""
    _apply_common(monkeypatch, persist_assistant_id=None)
    old, new = await _run_both_resume(dict(_RESUME_KW))
    _assert_parity(old, new)
    assert not any('"data-user-message-id"' in f for f in old)
    assert any('"chat_turn_id": "42:1700000000000"' in f for f in old)
