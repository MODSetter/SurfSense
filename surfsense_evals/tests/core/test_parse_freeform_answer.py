"""Tests for ``surfsense_evals.core.parse.freeform_answer``."""

from __future__ import annotations

import pytest

from surfsense_evals.core.parse.freeform_answer import extract_freeform_answer


class TestExtractFreeformAnswer:
    def test_empty_string_returns_empty(self) -> None:
        assert extract_freeform_answer("") == ""
        assert extract_freeform_answer("   \n\n  ") == ""

    def test_simple_answer_marker(self) -> None:
        assert extract_freeform_answer("Answer: 42") == "42"

    def test_final_answer_marker(self) -> None:
        assert extract_freeform_answer("Final answer: Paris") == "Paris"

    def test_the_answer_is_marker(self) -> None:
        assert extract_freeform_answer("The answer is: not answerable") == "not answerable"

    def test_multiline_picks_last_answer_marker(self) -> None:
        text = "Let me think...\nAnswer: 5\nAnswer: 7\n"
        assert extract_freeform_answer(text) == "7"

    def test_falls_back_to_last_nonempty_line(self) -> None:
        text = "Some thinking here.\n\n42"
        assert extract_freeform_answer(text) == "42"

    def test_strips_quotes(self) -> None:
        assert extract_freeform_answer('Answer: "Paris"') == "Paris"
        assert extract_freeform_answer("Answer: 'Paris'") == "Paris"

    def test_strips_backticks(self) -> None:
        assert extract_freeform_answer("Answer: `42`") == "42"

    def test_uses_fenced_block_when_no_marker(self) -> None:
        text = "Here's my response:\n```\nfinal value\n```\n"
        assert extract_freeform_answer(text) == "final value"

    def test_case_insensitive_markers(self) -> None:
        assert extract_freeform_answer("ANSWER: yes") == "yes"
        assert extract_freeform_answer("answer: no") == "no"

    @pytest.mark.parametrize("text,expected", [
        ("Answer: 1, 2, 3", "1, 2, 3"),
        ("Answer: 3.14", "3.14"),
        ("Answer:    spaced   ", "spaced"),
    ])
    def test_various_payloads(self, text: str, expected: str) -> None:
        assert extract_freeform_answer(text) == expected

    def test_inline_answer_after_thinking_trace(self) -> None:
        # Agent replies sometimes glue their thinking onto the same
        # line as the final "Answer: ..." marker (no newline before it).
        # The line-anchored regex misses this; the inline fallback
        # should still extract the right value.
        text = (
            "Need the Charlotte Bronte book title/year and the rank "
            "for a 128-foot NYC building.Answer: 128th"
        )
        assert extract_freeform_answer(text) == "128th"

    def test_inline_picks_last_inline_answer(self) -> None:
        text = "Thought: maybe Answer: 5 is right? Actually Answer: 7."
        assert extract_freeform_answer(text) == "7."

    def test_inline_does_not_override_proper_marker(self) -> None:
        # When a clean line-anchored "Answer: ..." exists, that wins.
        text = "Some preamble.Answer: 99\nAnswer: 42"
        assert extract_freeform_answer(text) == "42"
