"""Tests for the MCQ answer-letter extractor."""

from __future__ import annotations

import pytest

from surfsense_evals.core.parse import extract_answer_letter
from surfsense_evals.core.parse.answer_letter import AnswerLetterResult


@pytest.mark.parametrize(
    "text,expected_letter,expected_strategy",
    [
        ('```json\n{"step_by_step_thinking": "...", "answer_choice": "B"}\n```', "B", "json_envelope"),
        ('Reasoning... {"step_by_step_thinking": "x", "answer_choice": "C"}', "C", "json_envelope"),
        ("Long reasoning.\nAnswer: D", "D", "answer_line"),
        ("The correct answer is (A).", "A", "answer_line"),
        ("Final answer: e", "E", "answer_line"),
        ("Long reasoning.\n\nB", "B", "bare_letter"),
        ("Long reasoning.\n\n(C).", "C", "bare_letter"),
        ("", None, "none"),
        ("Just narrative without an answer.", None, "none"),
    ],
)
def test_extract_answer_letter(text, expected_letter, expected_strategy):
    result = extract_answer_letter(text)
    assert result == AnswerLetterResult(expected_letter, expected_strategy)
