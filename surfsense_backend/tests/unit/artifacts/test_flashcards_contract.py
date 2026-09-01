from __future__ import annotations

import json

import pytest

from app.artifacts.verification import service
from app.artifacts.verification.formats.flashcards import (
    FLASHCARDS_MAX_CARDS,
    check_flashcards_json,
    flashcards_to_markdown,
    parse_flashcards_deck,
)
from app.artifacts.verification.formats.registry import get_format_adapter
from app.artifacts.verification.receipt import read_receipt
from tests.utils.fake_sandbox import FakeSandboxSession


def _deck(**overrides):
    value = {
        "schema_version": 1,
        "title": "HTTP fundamentals",
        "cards": [
            {
                "front_markdown": "What does **HTTP** stand for?",
                "back_markdown": "Hypertext Transfer Protocol.",
                "hint_markdown": "It begins with Hypertext.",
            },
            {
                "front_markdown": "What is an idempotent method?",
                "back_markdown": "Repeated identical requests have the same effect.",
            },
        ],
    }
    value.update(overrides)
    return json.dumps(value, ensure_ascii=False).encode()


def test_parses_closed_version_one_deck_and_projects_deterministic_markdown():
    data = _deck()

    deck = parse_flashcards_deck(data)

    assert deck.title == "HTTP fundamentals"
    assert len(deck.cards) == 2
    assert check_flashcards_json(data).clean
    assert flashcards_to_markdown(data) == (
        "# HTTP fundamentals\n\n"
        "## Card 1\n\n"
        "### Front\n\n"
        "What does **HTTP** stand for?\n\n"
        "### Back\n\n"
        "Hypertext Transfer Protocol.\n\n"
        "### Hint\n\n"
        "It begins with Hypertext.\n\n"
        "## Card 2\n\n"
        "### Front\n\n"
        "What is an idempotent method?\n\n"
        "### Back\n\n"
        "Repeated identical requests have the same effect.\n"
    )


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
        (_deck(cards=[]), "between 2 and 100"),
        (
            _deck(
                cards=[
                    {"front_markdown": "Same", "back_markdown": "One"},
                    {"front_markdown": "  SAME  ", "back_markdown": "Two"},
                ]
            ),
            "duplicate fronts",
        ),
        (
            _deck(
                cards=[
                    {
                        "front_markdown": "[unsafe](https://example.com)",
                        "back_markdown": "One",
                    },
                    {"front_markdown": "Safe", "back_markdown": "Two"},
                ]
            ),
            "unsupported HTML, image, or link",
        ),
        (
            _deck(
                cards=[
                    {
                        "front_markdown": "One",
                        "back_markdown": "Answer",
                        "hint_markdown": None,
                    },
                    {"front_markdown": "Two", "back_markdown": "Answer"},
                ]
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
    cards = [
        {"front_markdown": f"Question {index}", "back_markdown": f"Answer {index}"}
        for index in range(FLASHCARDS_MAX_CARDS)
    ]

    assert check_flashcards_json(_deck(cards=cards)).clean


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
