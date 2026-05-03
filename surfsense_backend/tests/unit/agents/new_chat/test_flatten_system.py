"""Tests for ``FlattenSystemMessageMiddleware``.

The middleware exists to defend against Anthropic's "Found 5 cache_control
blocks" 400 when our deepagent middleware stack stacks 5+ text blocks on
the system message and the OpenRouter→Anthropic adapter redistributes
``cache_control`` across all of them. The flattening collapses every
all-text system content list to a single string before the LLM call.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.new_chat.middleware.flatten_system import (
    FlattenSystemMessageMiddleware,
    _flatten_text_blocks,
    _flattened_request,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _flatten_text_blocks — pure helper, the heart of the middleware.
# ---------------------------------------------------------------------------


class TestFlattenTextBlocks:
    def test_joins_text_blocks_with_double_newline(self) -> None:
        blocks = [
            {"type": "text", "text": "<surfsense base>"},
            {"type": "text", "text": "<filesystem section>"},
            {"type": "text", "text": "<skills section>"},
        ]
        assert (
            _flatten_text_blocks(blocks)
            == "<surfsense base>\n\n<filesystem section>\n\n<skills section>"
        )

    def test_handles_single_text_block(self) -> None:
        blocks = [{"type": "text", "text": "only one"}]
        assert _flatten_text_blocks(blocks) == "only one"

    def test_handles_empty_list(self) -> None:
        assert _flatten_text_blocks([]) == ""

    def test_passes_through_bare_string_blocks(self) -> None:
        # LangChain content can mix bare strings and dict blocks.
        blocks = ["raw string", {"type": "text", "text": "dict block"}]
        assert _flatten_text_blocks(blocks) == "raw string\n\ndict block"

    def test_returns_none_for_image_block(self) -> None:
        # System messages with images are rare — but we never want to
        # silently lose the image payload by joining as text.
        blocks = [
            {"type": "text", "text": "look at this"},
            {"type": "image_url", "image_url": {"url": "data:image/png..."}},
        ]
        assert _flatten_text_blocks(blocks) is None

    def test_returns_none_for_non_dict_non_str_block(self) -> None:
        blocks = [{"type": "text", "text": "hi"}, 42]  # type: ignore[list-item]
        assert _flatten_text_blocks(blocks) is None

    def test_returns_none_when_text_field_missing(self) -> None:
        blocks = [{"type": "text"}]  # no ``text`` key
        assert _flatten_text_blocks(blocks) is None

    def test_returns_none_when_text_is_not_string(self) -> None:
        blocks = [{"type": "text", "text": ["nested", "list"]}]
        assert _flatten_text_blocks(blocks) is None

    def test_drops_cache_control_from_inner_blocks(self) -> None:
        # The whole point: existing cache_control on inner blocks is
        # discarded so LiteLLM's ``cache_control_injection_points`` can
        # re-attach exactly one breakpoint after flattening.
        blocks = [
            {"type": "text", "text": "first"},
            {
                "type": "text",
                "text": "second",
                "cache_control": {"type": "ephemeral"},
            },
        ]
        flattened = _flatten_text_blocks(blocks)
        assert flattened == "first\n\nsecond"
        assert "cache_control" not in flattened  # type: ignore[operator]


# ---------------------------------------------------------------------------
# _flattened_request — decides when to override and when to no-op.
# ---------------------------------------------------------------------------


def _make_request(system_message: SystemMessage | None) -> Any:
    """Build a minimal ModelRequest stub. We only need .system_message
    and .override(system_message=...) — the middleware never touches
    other fields.
    """
    request = MagicMock()
    request.system_message = system_message

    def override(**kwargs: Any) -> Any:
        new_request = MagicMock()
        new_request.system_message = kwargs.get(
            "system_message", request.system_message
        )
        new_request.messages = kwargs.get("messages", getattr(request, "messages", []))
        new_request.tools = kwargs.get("tools", getattr(request, "tools", []))
        return new_request

    request.override = override
    return request


class TestFlattenedRequest:
    def test_collapses_multi_block_system_to_string(self) -> None:
        sys = SystemMessage(
            content=[
                {"type": "text", "text": "<base>"},
                {"type": "text", "text": "<todo>"},
                {"type": "text", "text": "<filesystem>"},
                {"type": "text", "text": "<skills>"},
                {"type": "text", "text": "<subagents>"},
            ]
        )
        request = _make_request(sys)
        flattened = _flattened_request(request)

        assert flattened is not None
        assert isinstance(flattened.system_message, SystemMessage)
        assert flattened.system_message.content == (
            "<base>\n\n<todo>\n\n<filesystem>\n\n<skills>\n\n<subagents>"
        )

    def test_no_op_for_string_content(self) -> None:
        sys = SystemMessage(content="already a string")
        request = _make_request(sys)
        assert _flattened_request(request) is None

    def test_no_op_for_single_block_list(self) -> None:
        # One block already produces one breakpoint — no need to flatten.
        sys = SystemMessage(content=[{"type": "text", "text": "single"}])
        request = _make_request(sys)
        assert _flattened_request(request) is None

    def test_no_op_when_system_message_missing(self) -> None:
        request = _make_request(None)
        assert _flattened_request(request) is None

    def test_no_op_when_list_contains_non_text_block(self) -> None:
        sys = SystemMessage(
            content=[
                {"type": "text", "text": "look"},
                {"type": "image_url", "image_url": {"url": "data:..."}},
            ]
        )
        request = _make_request(sys)
        assert _flattened_request(request) is None

    def test_preserves_additional_kwargs_and_metadata(self) -> None:
        # Defensive: nothing in the current chain sets these on a system
        # message, but losing them silently when something does in the
        # future would be a regression. ``name`` in particular is the only
        # ``additional_kwargs`` field that ChatLiteLLM's
        # ``_convert_message_to_dict`` propagates onto the wire.
        sys = SystemMessage(
            content=[
                {"type": "text", "text": "a"},
                {"type": "text", "text": "b"},
            ],
            additional_kwargs={"name": "surfsense_system", "x": 1},
            response_metadata={"tokens": 42},
        )
        sys.id = "sys-msg-1"
        request = _make_request(sys)

        flattened = _flattened_request(request)
        assert flattened is not None
        assert flattened.system_message.content == "a\n\nb"
        assert flattened.system_message.additional_kwargs == {
            "name": "surfsense_system",
            "x": 1,
        }
        assert flattened.system_message.response_metadata == {"tokens": 42}
        assert flattened.system_message.id == "sys-msg-1"

    def test_idempotent_when_run_twice(self) -> None:
        sys = SystemMessage(
            content=[
                {"type": "text", "text": "a"},
                {"type": "text", "text": "b"},
            ]
        )
        request = _make_request(sys)
        first = _flattened_request(request)
        assert first is not None

        # Second pass on the already-flattened request should be a no-op.
        # We re-wrap in a request stub since the helper inspects
        # ``request.system_message.content``.
        second_request = _make_request(first.system_message)
        assert _flattened_request(second_request) is None


# ---------------------------------------------------------------------------
# Middleware integration — verify the handler sees a flattened request.
# ---------------------------------------------------------------------------


class TestMiddlewareWrap:
    @pytest.mark.asyncio
    async def test_async_passes_flattened_request_to_handler(self) -> None:
        sys = SystemMessage(
            content=[
                {"type": "text", "text": "alpha"},
                {"type": "text", "text": "beta"},
            ]
        )
        request = _make_request(sys)
        captured: dict[str, Any] = {}

        async def handler(req: Any) -> str:
            captured["request"] = req
            return "ok"

        mw = FlattenSystemMessageMiddleware()
        result = await mw.awrap_model_call(request, handler)

        assert result == "ok"
        assert isinstance(captured["request"].system_message, SystemMessage)
        assert captured["request"].system_message.content == "alpha\n\nbeta"

    @pytest.mark.asyncio
    async def test_async_passes_through_when_already_string(self) -> None:
        sys = SystemMessage(content="just a string")
        request = _make_request(sys)
        captured: dict[str, Any] = {}

        async def handler(req: Any) -> str:
            captured["request"] = req
            return "ok"

        mw = FlattenSystemMessageMiddleware()
        await mw.awrap_model_call(request, handler)

        # Same request object: no override happened.
        assert captured["request"] is request

    def test_sync_passes_flattened_request_to_handler(self) -> None:
        sys = SystemMessage(
            content=[
                {"type": "text", "text": "alpha"},
                {"type": "text", "text": "beta"},
            ]
        )
        request = _make_request(sys)
        captured: dict[str, Any] = {}

        def handler(req: Any) -> str:
            captured["request"] = req
            return "ok"

        mw = FlattenSystemMessageMiddleware()
        result = mw.wrap_model_call(request, handler)

        assert result == "ok"
        assert captured["request"].system_message.content == "alpha\n\nbeta"

    def test_sync_passes_through_when_no_system_message(self) -> None:
        request = _make_request(None)
        captured: dict[str, Any] = {}

        def handler(req: Any) -> str:
            captured["request"] = req
            return "ok"

        mw = FlattenSystemMessageMiddleware()
        mw.wrap_model_call(request, handler)
        assert captured["request"] is request


# ---------------------------------------------------------------------------
# Regression guard — pin the worst-case shape that triggered the
# "Found 5" 400 in production. Confirms we collapse 5 blocks to 1 so the
# downstream cache_control_injection_points can only place 1 breakpoint
# on the system message regardless of provider redistribution quirks.
# ---------------------------------------------------------------------------


def test_regression_five_block_system_collapses_to_one_block() -> None:
    sys = SystemMessage(
        content=[
            {"type": "text", "text": "<surfsense base + BASE_AGENT_PROMPT>"},
            {"type": "text", "text": "<TodoListMiddleware section>"},
            {"type": "text", "text": "<SurfSenseFilesystemMiddleware section>"},
            {"type": "text", "text": "<SkillsMiddleware section>"},
            {"type": "text", "text": "<SubAgentMiddleware section>"},
        ]
    )
    request = _make_request(sys)
    flattened = _flattened_request(request)

    assert flattened is not None
    assert isinstance(flattened.system_message.content, str)
    # The exact join doesn't matter for the cache_control accounting —
    # only that there is exactly ONE content block when LiteLLM's
    # AnthropicCacheControlHook later targets ``role: system``.
    assert "<surfsense base" in flattened.system_message.content
    assert "<SubAgentMiddleware" in flattened.system_message.content


def test_regression_human_message_not_modified() -> None:
    # Sanity: the middleware MUST NOT touch user messages — only the
    # system message. Multi-block user content is the path that carries
    # image attachments and would lose its image_url block on
    # accidental flatten.
    sys = SystemMessage(
        content=[
            {"type": "text", "text": "a"},
            {"type": "text", "text": "b"},
        ]
    )
    user = HumanMessage(
        content=[
            {"type": "text", "text": "look at this"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}},
        ]
    )
    request = _make_request(sys)
    request.messages = [user]

    flattened = _flattened_request(request)
    assert flattened is not None
    # System flattened to string …
    assert isinstance(flattened.system_message.content, str)
    # … user message is untouched (the helper does not even look at it).
    assert flattened.messages == [user]
    assert isinstance(user.content, list)
    assert len(user.content) == 2
