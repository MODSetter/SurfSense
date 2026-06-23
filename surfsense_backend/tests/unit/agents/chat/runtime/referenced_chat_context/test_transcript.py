"""Tests for referenced-chat transcript rendering and token budgeting."""

from __future__ import annotations

import pytest

from app.agents.chat.runtime.referenced_chat_context import (
    ReferencedChat,
    render_referenced_chats_block,
)
from app.agents.chat.runtime.referenced_chat_context import transcript as transcript_mod
from app.agents.chat.runtime.referenced_chat_context.models import ReferencedChatTurn

pytestmark = pytest.mark.unit


def _chat(thread_id: int, title: str, turns: list[tuple[str, str]]) -> ReferencedChat:
    return ReferencedChat(
        thread_id=thread_id,
        title=title,
        turns=[ReferencedChatTurn(role=role, text=text) for role, text in turns],
    )


def test_returns_none_when_no_chats() -> None:
    assert render_referenced_chats_block([]) is None


def test_renders_header_chat_tag_and_turns_in_order() -> None:
    block = render_referenced_chats_block(
        [_chat(7, "Roadmap", [("user", "hi"), ("assistant", "hello")])]
    )

    assert block is not None
    assert block.startswith("<referenced_chat_context>")
    assert block.endswith("</referenced_chat_context>")
    assert '<chat thread_id="7" title="Roadmap">' in block
    # Chronological order is preserved.
    assert block.index("user: hi") < block.index("assistant: hello")
    assert "</chat>" in block


def test_escapes_special_characters_in_title() -> None:
    block = render_referenced_chats_block([_chat(1, '<a> & "b"', [("user", "q")])])

    assert block is not None
    assert 'title="&lt;a&gt; &amp; &quot;b&quot;">' in block
    # Raw, unescaped title must never reach the attribute.
    assert '<a> & "b"' not in block


def test_budget_keeps_recent_turns_and_marks_truncation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Each line below is ~10 chars; a 25-char budget fits two short lines.
    monkeypatch.setattr(transcript_mod, "_MAX_CHARS_PER_REFERENCE", 25)

    block = render_referenced_chats_block(
        [
            _chat(
                1,
                "T",
                [("user", "aaaa"), ("assistant", "bbbb"), ("user", "cccc")],
            )
        ]
    )

    assert block is not None
    # Oldest turn dropped, marker prepended, remaining turns chronological.
    assert transcript_mod._TRUNCATION_MARKER in block
    assert "user: aaaa" not in block
    assert block.index("assistant: bbbb") < block.index("user: cccc")


def test_oversized_single_turn_is_partially_filled_to_use_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(transcript_mod, "_MAX_CHARS_PER_REFERENCE", 40)

    block = render_referenced_chats_block(
        [_chat(1, "T", [("assistant", "x" * 500)])]
    )

    assert block is not None
    # The turn is too big to keep whole, so its tail fills the budget with a
    # role label, a mid-turn "…" marker, and a block-level truncation marker.
    assert "assistant: \u2026" in block
    assert transcript_mod._TRUNCATION_MARKER in block
    assert "x" * 500 not in block
    # The partial turn line never exceeds the budget.
    turn_line = next(
        line for line in block.splitlines() if line.startswith("assistant: ")
    )
    assert len(turn_line) <= 40


def test_overflowing_older_turn_fills_remaining_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(transcript_mod, "_MAX_CHARS_PER_REFERENCE", 40)

    block = render_referenced_chats_block(
        [_chat(1, "T", [("user", "y" * 100), ("assistant", "zzzz")])]
    )

    assert block is not None
    # Newest turn kept whole; leftover budget filled with the older turn's tail
    # instead of dropping it entirely.
    assert "assistant: zzzz" in block
    assert "user: \u2026" in block
    assert transcript_mod._TRUNCATION_MARKER in block
    # Chronological order: partial older turn precedes the newest turn.
    assert block.index("user: \u2026") < block.index("assistant: zzzz")


def test_renders_multiple_chats_each_in_own_tag() -> None:
    block = render_referenced_chats_block(
        [
            _chat(1, "First", [("user", "one")]),
            _chat(2, "Second", [("user", "two")]),
        ]
    )

    assert block is not None
    assert '<chat thread_id="1" title="First">' in block
    assert '<chat thread_id="2" title="Second">' in block
    assert block.count("</chat>") == 2
