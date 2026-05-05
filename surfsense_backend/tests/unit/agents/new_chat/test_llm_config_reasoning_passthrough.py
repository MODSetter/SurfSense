"""Regression tests for issue #1333 — DeepSeek ``reasoning_content`` lost
on Turn 2 of multi-turn agent runs.

The bug shape: after Turn 1, langchain-litellm's ``_convert_message_to_dict``
serializes the prior ``AIMessage`` for the next outbound request and silently
drops every ``additional_kwargs`` key except ``function_call`` /
``tool_calls`` / ``name``. DeepSeek's thinking-mode contract requires the
``reasoning_content`` field to be echoed back verbatim — without it the API
rejects the request with ``400 BadRequestError: The reasoning_content in the
thinking mode must be passed back to the API``.

This module pins the three things that have to hold for Turn 2 to land:

1. ``_sanitize_messages`` does not mutate the input messages in place — the
   instances persisted in LangGraph state survive untouched, so the same
   ``content`` blocks (incl. ``thinking``) remain available on the next
   sanitize cycle.
2. ``_extract_reasoning_content_from_blocks`` recovers the reasoning string
   from langchain-litellm's standard ``{"type": "thinking", ...}`` content
   blocks when ``additional_kwargs["reasoning_content"]`` is missing
   (state-persistence layers that drop ``additional_kwargs`` but keep
   content blocks).
3. ``SanitizedChatLiteLLM._create_message_dicts`` re-attaches
   ``reasoning_content`` onto the dict langchain-litellm sends to the
   provider.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.agents.new_chat.llm_config import (
    SanitizedChatLiteLLM,
    _attach_reasoning_passthrough,
    _extract_reasoning_content_from_blocks,
    _sanitize_messages,
)

pytestmark = pytest.mark.unit


class TestSanitizeMessagesNoMutation:
    """``_sanitize_messages`` must not mutate the inputs.

    The same ``BaseMessage`` instances live in LangGraph's persisted state
    in many of SurfSense's agent paths. In-place mutation of ``msg.content``
    corrupts that state — once ``thinking`` blocks are stripped from the
    persisted message, Turn 2's reasoning-content recovery has nothing to
    fall back to.
    """

    def test_thinking_block_preserved_in_original_aimessage(self) -> None:
        """Stripping ``thinking`` for the outbound payload must not touch the
        AIMessage held by graph state."""
        original_content = [
            {"type": "thinking", "thinking": "step 1: pick a tool"},
            {"type": "text", "text": "I'll search the docs."},
        ]
        ai = AIMessage(
            content=list(original_content),
            additional_kwargs={"reasoning_content": "step 1: pick a tool"},
        )
        sanitized = _sanitize_messages([ai])

        assert sanitized[0] is not ai, (
            "_sanitize_messages must return new instances, not the originals"
        )
        # Original survives intact — graph state is safe.
        assert ai.content == original_content
        assert ai.additional_kwargs == {"reasoning_content": "step 1: pick a tool"}

    def test_aimessage_with_only_tool_calls_collapses_to_none_outbound(self) -> None:
        """Outbound: AIMessage with no text content + tool_calls collapses to
        ``None`` (Bedrock-friendly). Original AIMessage stays unchanged."""
        ai = AIMessage(
            content=[],
            tool_calls=[
                {"id": "c1", "name": "search", "args": {"q": "x"}},
            ],
        )
        sanitized = _sanitize_messages([ai])
        assert sanitized[0].content is None
        # Original remains a list — graph state is not corrupted.
        assert ai.content == []

    def test_humanmessage_passthrough_returns_new_instance(self) -> None:
        h = HumanMessage(content="hello")
        sanitized = _sanitize_messages([h])
        assert sanitized[0].content == "hello"
        assert sanitized[0] is not h

    def test_string_content_left_alone(self) -> None:
        ai = AIMessage(content="plain assistant reply")
        sanitized = _sanitize_messages([ai])
        assert sanitized[0].content == "plain assistant reply"
        # Underlying object still untouched.
        assert ai.content == "plain assistant reply"

    def test_provider_specific_blocks_stripped_on_outbound(self) -> None:
        """The original behaviour — ``thinking`` blocks must NOT appear on
        the outbound message — has to keep working after the no-mutation
        refactor."""
        ai = AIMessage(
            content=[
                {"type": "thinking", "thinking": "private chain of thought"},
                {"type": "text", "text": "visible answer"},
            ]
        )
        sanitized = _sanitize_messages([ai])
        # Single text block collapses to a plain string per _sanitize_content.
        assert sanitized[0].content == "visible answer"


class TestExtractReasoningContentFromBlocks:
    """``_extract_reasoning_content_from_blocks`` is the fallback used when
    ``additional_kwargs["reasoning_content"]`` is gone but the content blocks
    survived.
    """

    def test_thinking_block_returns_text(self) -> None:
        content = [
            {"type": "thinking", "thinking": "consider option A first"},
            {"type": "text", "text": "I will use tool X"},
        ]
        assert (
            _extract_reasoning_content_from_blocks(content) == "consider option A first"
        )

    def test_multiple_thinking_blocks_concatenate(self) -> None:
        content = [
            {"type": "thinking", "thinking": "first thought."},
            {"type": "thinking", "thinking": "second thought."},
            {"type": "text", "text": "answer"},
        ]
        assert (
            _extract_reasoning_content_from_blocks(content)
            == "first thought.second thought."
        )

    def test_redacted_thinking_uses_data_field(self) -> None:
        content = [
            {"type": "redacted_thinking", "data": "<opaque-base64-blob>"},
            {"type": "text", "text": "answer"},
        ]
        assert _extract_reasoning_content_from_blocks(content) == "<opaque-base64-blob>"

    def test_no_thinking_blocks_returns_none(self) -> None:
        content = [{"type": "text", "text": "answer"}]
        assert _extract_reasoning_content_from_blocks(content) is None

    def test_string_content_returns_none(self) -> None:
        assert _extract_reasoning_content_from_blocks("just a string") is None

    def test_none_returns_none(self) -> None:
        assert _extract_reasoning_content_from_blocks(None) is None

    def test_empty_thinking_text_skipped(self) -> None:
        content = [
            {"type": "thinking", "thinking": ""},
            {"type": "text", "text": "answer"},
        ]
        assert _extract_reasoning_content_from_blocks(content) is None

    def test_non_dict_blocks_skipped(self) -> None:
        content = [
            "stray bare string",
            {"type": "thinking", "thinking": "real reasoning"},
        ]
        assert _extract_reasoning_content_from_blocks(content) == "real reasoning"


class TestAttachReasoningPassthrough:
    """``_attach_reasoning_passthrough`` is the surgical patch over
    langchain-litellm's ``_convert_message_to_dict`` drop. It must:

    * Inject ``reasoning_content`` from ``additional_kwargs`` when present.
    * Fall back to ``content`` blocks when ``additional_kwargs`` is empty.
    * Leave non-AIMessage entries alone.
    * Be a no-op when no reasoning is available anywhere.
    """

    def test_kwargs_value_wins_when_present(self) -> None:
        ai = AIMessage(
            content="plain text",
            additional_kwargs={"reasoning_content": "from kwargs"},
        )
        msg_dict: dict = {"role": "assistant", "content": "plain text"}
        _attach_reasoning_passthrough([ai], [msg_dict])
        assert msg_dict["reasoning_content"] == "from kwargs"

    def test_falls_back_to_thinking_block_when_kwargs_missing(self) -> None:
        ai = AIMessage(
            content=[
                {"type": "thinking", "thinking": "reasoning lost from kwargs"},
                {"type": "text", "text": "answer"},
            ],
            additional_kwargs={},
        )
        msg_dict: dict = {"role": "assistant", "content": "answer"}
        _attach_reasoning_passthrough([ai], [msg_dict])
        assert msg_dict["reasoning_content"] == "reasoning lost from kwargs"

    def test_no_op_when_no_reasoning_anywhere(self) -> None:
        ai = AIMessage(content="answer", additional_kwargs={})
        msg_dict: dict = {"role": "assistant", "content": "answer"}
        _attach_reasoning_passthrough([ai], [msg_dict])
        assert "reasoning_content" not in msg_dict

    def test_non_aimessage_entries_skipped(self) -> None:
        h = HumanMessage(content="hi")
        msg_dict: dict = {"role": "user", "content": "hi"}
        _attach_reasoning_passthrough([h], [msg_dict])
        assert "reasoning_content" not in msg_dict

    def test_kwargs_with_empty_reasoning_falls_through_to_blocks(self) -> None:
        """A persisted-but-emptied ``reasoning_content`` (some serializers
        replace missing keys with ``None``) must still trigger the fallback."""
        ai = AIMessage(
            content=[
                {"type": "thinking", "thinking": "recovered from blocks"},
                {"type": "text", "text": "answer"},
            ],
            additional_kwargs={"reasoning_content": None},
        )
        msg_dict: dict = {"role": "assistant", "content": "answer"}
        _attach_reasoning_passthrough([ai], [msg_dict])
        assert msg_dict["reasoning_content"] == "recovered from blocks"

    def test_mismatched_lengths_is_safe_noop(self) -> None:
        """If something upstream produced a different-length message_dicts
        list, we must not crash — just skip the passthrough."""
        ai = AIMessage(content="x", additional_kwargs={"reasoning_content": "abc"})
        msg_dicts: list[dict] = []
        _attach_reasoning_passthrough([ai], msg_dicts)
        assert msg_dicts == []

    def test_aligned_zip_across_mixed_messages(self) -> None:
        """The injection must only land on AIMessage rows — for the
        round-trip through ``zip`` to be safe across mixed conversations."""
        msgs: list[BaseMessage] = [
            HumanMessage(content="q1"),
            AIMessage(content="a1", additional_kwargs={"reasoning_content": "r1"}),
            HumanMessage(content="q2"),
        ]
        dicts: list[dict] = [
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "q2"},
        ]
        _attach_reasoning_passthrough(msgs, dicts)
        assert "reasoning_content" not in dicts[0]
        assert dicts[1]["reasoning_content"] == "r1"
        assert "reasoning_content" not in dicts[2]


class TestSanitizedChatLiteLLMCreateMessageDicts:
    """End-to-end pin: ``SanitizedChatLiteLLM._create_message_dicts`` must
    return outbound dicts with ``reasoning_content`` re-attached, exactly as
    DeepSeek requires on Turn 2.

    We patch ``ChatLiteLLM._create_message_dicts`` to verify our override
    consults the real langchain-litellm implementation (which drops the
    field) and then re-injects it. This pins the boundary between SurfSense
    and the upstream library — if upstream ever starts forwarding
    ``reasoning_content`` itself, this test will keep passing because our
    re-injection is idempotent.
    """

    def test_create_message_dicts_restores_reasoning_content(self) -> None:
        # We can't construct a real ChatLiteLLM without a model + key, so
        # bypass __init__ and call the bound method on a synthetic instance.
        llm = SanitizedChatLiteLLM.__new__(SanitizedChatLiteLLM)
        msgs: list[BaseMessage] = [
            HumanMessage(content="search the docs for X"),
            AIMessage(
                content=[
                    {"type": "thinking", "thinking": "I should call search"},
                    {"type": "text", "text": "calling search"},
                ],
                additional_kwargs={"reasoning_content": "I should call search"},
                tool_calls=[{"id": "c1", "name": "search", "args": {"q": "X"}}],
            ),
        ]

        def fake_super_create(self, sanitized_msgs, stop):
            # Mirror what real langchain-litellm ``_convert_message_to_dict``
            # produces: tool_calls preserved, reasoning_content dropped.
            out: list[dict] = []
            for msg in sanitized_msgs:
                if isinstance(msg, HumanMessage):
                    out.append({"role": "user", "content": msg.content})
                elif isinstance(msg, AIMessage):
                    out.append(
                        {
                            "role": "assistant",
                            "content": msg.content,
                            "tool_calls": msg.tool_calls,
                        }
                    )
            return out, {"stream": False}

        with patch(
            "app.agents.new_chat.llm_config.ChatLiteLLM._create_message_dicts",
            new=fake_super_create,
        ):
            dicts, params = SanitizedChatLiteLLM._create_message_dicts(llm, msgs, None)

        # AIMessage dict has reasoning_content re-attached — DeepSeek won't
        # 400 on Turn 2.
        assert dicts[1]["reasoning_content"] == "I should call search"
        # tool_calls untouched — single source of truth still langchain.
        assert dicts[1]["tool_calls"][0]["name"] == "search"
        # User message dict has no reasoning_content key at all.
        assert "reasoning_content" not in dicts[0]
        # Params from upstream surface unchanged.
        assert params == {"stream": False}

    def test_create_message_dicts_recovers_when_kwargs_dropped(self) -> None:
        """The state-persistence-loss case: ``additional_kwargs`` is empty
        post-roundtrip, but the ``thinking`` block in ``content`` survives.
        """
        llm = SanitizedChatLiteLLM.__new__(SanitizedChatLiteLLM)
        msgs: list[BaseMessage] = [
            AIMessage(
                content=[
                    {"type": "thinking", "thinking": "post-restore reasoning"},
                    {"type": "text", "text": "ok"},
                ],
                additional_kwargs={},  # <-- the issue #1333 root cause
                tool_calls=[{"id": "c1", "name": "search", "args": {"q": "X"}}],
            ),
        ]

        def fake_super_create(self, sanitized_msgs, stop):
            out = [
                {
                    "role": "assistant",
                    "content": sanitized_msgs[0].content,
                    "tool_calls": sanitized_msgs[0].tool_calls,
                }
            ]
            return out, {}

        with patch(
            "app.agents.new_chat.llm_config.ChatLiteLLM._create_message_dicts",
            new=fake_super_create,
        ):
            dicts, _ = SanitizedChatLiteLLM._create_message_dicts(llm, msgs, None)

        assert dicts[0]["reasoning_content"] == "post-restore reasoning"
