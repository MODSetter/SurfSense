from __future__ import annotations

import json

import pytest

from app.artifacts.verification.formats.quiz import (
    QUIZ_MAX_QUESTIONS,
    QUIZ_MIN_QUESTIONS,
    check_quiz_json,
    parse_quiz,
    quiz_to_markdown,
)
from app.artifacts.verification.formats.registry import get_format_adapter


def _questions(count=QUIZ_MIN_QUESTIONS):
    return [
        {
            "question_text": f"Question {index}",
            "options": [f"A {index}", f"B {index}", f"C {index}", f"D {index}"],
            "correct_option_index": index % 4,
            "explanation_text": f"Explanation {index}",
        }
        for index in range(1, count + 1)
    ]


def _quiz(**overrides):
    value = {
        "schema_version": 1,
        "title": "HTTP fundamentals",
        "questions": _questions(),
    }
    value.update(overrides)
    return json.dumps(value, ensure_ascii=False).encode()


def test_parses_closed_quiz_and_projects_markdown():
    quiz = parse_quiz(_quiz())
    markdown = quiz_to_markdown(_quiz())

    assert len(quiz.questions) == QUIZ_MIN_QUESTIONS
    assert markdown.startswith("# HTTP fundamentals\n\n## Question 1")
    assert "### Correct answer" in markdown
    assert markdown.endswith("\n")
    assert check_quiz_json(_quiz()).clean


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"", "empty"),
        (b"\xef\xbb\xbf{}", "byte-order mark"),
        (b'{"schema_version":1,"schema_version":1}', "duplicate JSON key"),
        (_quiz(schema_version=2), "schema_version"),
        (_quiz(extra=True), "Extra inputs"),
        (_quiz(questions=_questions(QUIZ_MIN_QUESTIONS - 1)), "between 5 and 30"),
        (_quiz(questions=_questions(QUIZ_MAX_QUESTIONS + 1)), "between 5 and 30"),
        (
            _quiz(
                questions=[
                    {
                        **_questions()[0],
                        "options": ["A", "B", "C"],
                    },
                    *_questions()[1:],
                ]
            ),
            "exactly four",
        ),
        (
            _quiz(
                questions=[
                    {
                        **_questions()[0],
                        "options": ["Same", " same ", "C", "D"],
                    },
                    *_questions()[1:],
                ]
            ),
            "distinct",
        ),
        (
            _quiz(
                questions=[
                    {**_questions()[0], "correct_option_index": 4},
                    *_questions()[1:],
                ]
            ),
            "less than or equal to 3",
        ),
        (
            _quiz(
                questions=[
                    {**_questions()[0], "question_text": r"Bad \(x"},
                    *_questions()[1:],
                ]
            ),
            "unclosed LaTeX",
        ),
    ],
)
def test_rejects_invalid_quizzes(data: bytes, message: str):
    result = check_quiz_json(data)
    assert not result.clean
    assert message in result.findings[0]


def test_quiz_adapter_is_programmatic_and_projection_backed():
    adapter = get_format_adapter("quiz")
    assert adapter.suffix == ".json"
    assert adapter.mime_type == "application/json"
    assert adapter.requires_visual_review is False
    assert adapter.markdown_projection is quiz_to_markdown
