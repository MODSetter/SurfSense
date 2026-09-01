from __future__ import annotations

import json

import pytest

from app.artifacts.verification import service
from app.artifacts.verification.formats.flashcards import (
    FLASHCARDS_MAX_CARDS,
    FLASHCARDS_MIN_CARDS,
    check_flashcards_json,
    flashcards_to_markdown,
    parse_flashcards_deck,
)
from app.artifacts.verification.formats.registry import get_format_adapter
from app.artifacts.verification.receipt import read_receipt
from tests.utils.fake_sandbox import FakeSandboxSession


def _cards(count=FLASHCARDS_MIN_CARDS, *, start=1):
    return [
        {
            "front_text": f"Question {index}",
            "back_text": f"Answer {index}",
        }
        for index in range(start, start + count)
    ]


def _padded_cards(*leading):
    return [
        *leading,
        *_cards(FLASHCARDS_MIN_CARDS - len(leading), start=len(leading) + 1),
    ]


def _deck(**overrides):
    value = {
        "schema_version": 1,
        "title": "HTTP fundamentals",
        "cards": _cards(),
    }
    value.update(overrides)
    return json.dumps(value, ensure_ascii=False).encode()


def test_parses_closed_version_one_deck_and_projects_deterministic_markdown():
    data = _deck()

    deck = parse_flashcards_deck(data)
    markdown = flashcards_to_markdown(data)

    assert deck.title == "HTTP fundamentals"
    assert len(deck.cards) == FLASHCARDS_MIN_CARDS
    assert check_flashcards_json(data).clean
    assert markdown.startswith(
        "# HTTP fundamentals\n\n"
        "## Card 1\n\n"
        "### Front\n\n"
        "Question 1\n\n"
        "### Back\n\n"
        "Answer 1\n"
    )
    assert markdown.endswith(
        f"## Card {FLASHCARDS_MIN_CARDS}\n\n"
        "### Front\n\n"
        f"Question {FLASHCARDS_MIN_CARDS}\n\n"
        "### Back\n\n"
        f"Answer {FLASHCARDS_MIN_CARDS}\n"
    )
    assert markdown.count("## Card ") == FLASHCARDS_MIN_CARDS


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"", "empty"),
        (b"\xef\xbb\xbf{}", "byte-order mark"),
        (b"\xff", "UTF-8"),
        (b'{"schema_version":1,"schema_version":1}', "duplicate JSON key"),
        (b'{"schema_version":NaN}', "unsupported JSON number"),
        (_deck(schema_version=2), "schema_version"),
        (_deck(schema_version=True), "schema_version"),
        (_deck(extra=True), "Extra inputs"),
        (
            _deck(cards=_cards(FLASHCARDS_MIN_CARDS - 1)),
            "between 15 and 100",
        ),
        (
            _deck(
                cards=_padded_cards(
                    {"front_text": "Same", "back_text": "One"},
                    {"front_text": "  SAME  ", "back_text": "Two"},
                )
            ),
            "duplicate fronts",
        ),
        (
            _deck(
                cards=_padded_cards(
                    {
                        "front_text": r"Calculate \(x",
                        "back_text": "One",
                    },
                )
            ),
            "unclosed LaTeX delimiter",
        ),
        (
            _deck(
                cards=_padded_cards(
                    {"front_text": r"Calculate \(x\]", "back_text": "One"},
                )
            ),
            "mismatched LaTeX delimiters",
        ),
        (
            _deck(
                cards=_padded_cards(
                    {"front_text": r"Calculate \(\)", "back_text": "One"},
                )
            ),
            "empty LaTeX expression",
        ),
        (
            _deck(
                cards=_padded_cards(
                    {"front_text": r"Calculate \(x_{1\)", "back_text": "One"},
                )
            ),
            "unbalanced LaTeX braces",
        ),
        (
            _deck(
                cards=_padded_cards(
                    {"front_text": r"Calculate \(x \[y\]\)", "back_text": "One"},
                )
            ),
            "nested LaTeX delimiters",
        ),
        (
            _deck(
                cards=_padded_cards(
                    {
                        "front_text": "One",
                        "back_text": "Answer",
                        "hint_text": None,
                    },
                )
            ),
            "must be omitted",
        ),
    ],
)
def test_rejects_invalid_or_unsafe_decks(data: bytes, message: str):
    result = check_flashcards_json(data)

    assert not result.clean
    assert message in result.findings[0]


def test_accepts_upper_card_bound():
    cards = _cards(FLASHCARDS_MAX_CARDS)

    assert check_flashcards_json(_deck(cards=cards)).clean


def test_plain_text_is_escaped_for_indexing_while_latex_is_preserved():
    data = _deck(
        cards=_padded_cards(
            {
                "front_text": r"What does \(T_a\) represent?",
                "back_text": r"# Ambient [temperature] \(T_a\)",
                "hint_text": r"Use \[T(t)=T_a+(T_0-T_a)e^{-kt}\]",
            },
        )
    )

    markdown = flashcards_to_markdown(data)

    assert r"What does \(T_a\) represent?" in markdown
    assert r"\# Ambient \[temperature\] \(T_a\)" in markdown
    assert "\\[\nT(t)=T_a+(T_0-T_a)e^{-kt}\n\\]" in markdown


async def test_flashcards_adapter_skips_render_and_vision():
    path = "/workspace/deck.json"
    session = FakeSandboxSession({path: _deck()})
    adapter = get_format_adapter("flashcards")

    result = await service.verify_artifact(
        session,
        path,
        format="flashcards",
        workspace_id=7,
        vision_llm=object(),
        secret_key="test-secret",
    )
    receipt = await read_receipt(
        session,
        "test-secret",
        workspace_id=7,
        primary_path=path,
    )

    assert adapter.suffix == ".json"
    assert adapter.mime_type == "application/json"
    assert adapter.markdown_projection is flashcards_to_markdown
    assert result.verified
    assert receipt.format == "flashcards"
    assert receipt.visual == "not_required"
    assert receipt.preview_path is None
    assert receipt.markdown_representation_sha256 is None
    assert not any(
        "soffice" in command or "pdftoppm" in command for command in session.commands
    )
