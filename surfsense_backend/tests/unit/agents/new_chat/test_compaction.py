"""Tests for SurfSenseCompactionMiddleware: protected SystemMessage handling and content sanitization."""

from __future__ import annotations

import pytest
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from app.agents.new_chat.middleware.compaction import (
    PROTECTED_SYSTEM_PREFIXES,
    _is_protected_system_message,
    _sanitize_message_content,
)

pytestmark = pytest.mark.unit


class TestIsProtectedSystemMessage:
    @pytest.mark.parametrize("prefix", PROTECTED_SYSTEM_PREFIXES)
    def test_each_prefix_protected(self, prefix: str) -> None:
        msg = SystemMessage(content=f"{prefix}\nbody\n</close>")
        assert _is_protected_system_message(msg) is True

    def test_unprotected_system_message(self) -> None:
        assert (
            _is_protected_system_message(SystemMessage(content="random instructions"))
            is False
        )

    def test_human_message_never_protected(self) -> None:
        assert (
            _is_protected_system_message(HumanMessage(content="<workspace_tree>..."))
            is False
        )

    def test_tolerates_leading_whitespace(self) -> None:
        msg = SystemMessage(content="   \n<priority_documents>\n...")
        assert _is_protected_system_message(msg) is True


class TestSanitizeMessageContent:
    def test_returns_same_message_when_content_present(self) -> None:
        msg = AIMessage(content="hello")
        assert _sanitize_message_content(msg) is msg

    def test_replaces_none_with_empty_string(self) -> None:
        # Pydantic blocks ``content=None`` at construction; the real
        # crash happens when the streaming layer mutates ``content``
        # after-the-fact. Replicate that by force-setting on a built
        # message.
        msg = AIMessage(
            content="",
            tool_calls=[{"name": "x", "args": {}, "id": "1"}],
        )
        # Bypass pydantic validation to simulate the LiteLLM/Bedrock case
        object.__setattr__(msg, "content", None)
        sanitized = _sanitize_message_content(msg)
        assert sanitized.content == ""


class TestPartitionMessages:
    """Verify the partition override surfaces protected SystemMessages
    into ``preserved_messages`` regardless of cutoff position.
    """

    def _build_partitioner(self):
        # Construct a thin shim — we can't easily instantiate the full
        # SurfSenseCompactionMiddleware without a real model, but the
        # override path needs ``_lc_helper`` to delegate to. We mock
        # that with a simple slicing partitioner equivalent to the real one.
        from app.agents.new_chat.middleware.compaction import (
            SurfSenseCompactionMiddleware,
        )

        class _LcHelper:
            @staticmethod
            def _partition_messages(messages, cutoff):
                return messages[:cutoff], messages[cutoff:]

        class _Stub(SurfSenseCompactionMiddleware):
            def __init__(self):
                self._lc_helper = _LcHelper()

        return _Stub()

    def test_protected_system_message_preserved_even_in_summarize_half(self) -> None:
        partitioner = self._build_partitioner()
        protected = SystemMessage(content="<priority_documents>\n...")
        msgs = [
            HumanMessage(content="old human"),
            AIMessage(content="old ai"),
            protected,
            ToolMessage(content="tool 1", tool_call_id="t1"),
            HumanMessage(content="new"),
        ]
        # Cutoff = 4 means everything before index 4 should be summarized
        to_summary, preserved = partitioner._partition_messages(msgs, 4)

        assert protected not in to_summary
        assert protected in preserved
        # The non-protected old messages remain in to_summary
        assert any(
            isinstance(m, HumanMessage) and m.content == "old human" for m in to_summary
        )

    def test_unprotected_messages_unaffected(self) -> None:
        partitioner = self._build_partitioner()
        msgs = [
            HumanMessage(content="a"),
            HumanMessage(content="b"),
            HumanMessage(content="c"),
        ]
        to_summary, preserved = partitioner._partition_messages(msgs, 2)
        assert [m.content for m in to_summary] == ["a", "b"]
        assert [m.content for m in preserved] == ["c"]
