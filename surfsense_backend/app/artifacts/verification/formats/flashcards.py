"""Strict structural checks and indexing projection for flashcard decks."""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationError,
    field_validator,
    model_validator,
)

from .base import StructuralCheckResult

FLASHCARDS_MIN_CARDS = 2
FLASHCARDS_MAX_CARDS = 100
FLASHCARDS_MAX_TITLE_CHARS = 200
FLASHCARDS_MAX_FRONT_CHARS = 4_000
FLASHCARDS_MAX_BACK_CHARS = 12_000
FLASHCARDS_MAX_HINT_CHARS = 2_000

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_RAW_HTML_RE = re.compile(r"<[^>\n]+>")
_IMAGE_RE = re.compile(r"!\[[^\]]*\](?:\([^)]*\)|\[[^\]]*\])")
_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\](?:\([^)]*\)|\[[^\]]*\])")
_REFERENCE_RE = re.compile(r"^\s*\[[^\]]+\]:\s*\S+", re.MULTILINE)
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}(?:\s+|$)", re.MULTILINE)
_SETEXT_HEADING_RE = re.compile(r"^\s*(?:=+|-+)\s*$", re.MULTILINE)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"unsupported JSON number: {value}")


def _validate_markdown(value: str, *, field: str, maximum: int) -> str:
    if not value.strip():
        raise ValueError(f"{field} must not be empty")
    if len(value) > maximum:
        raise ValueError(f"{field} exceeds {maximum} characters")
    if _CONTROL_RE.search(value):
        raise ValueError(f"{field} contains unsupported control characters")
    if (
        _RAW_HTML_RE.search(value)
        or _IMAGE_RE.search(value)
        or _LINK_RE.search(value)
        or _REFERENCE_RE.search(value)
    ):
        raise ValueError(f"{field} contains unsupported HTML, image, or link markup")
    if _HEADING_RE.search(value) or _SETEXT_HEADING_RE.search(value):
        raise ValueError(f"{field} contains unsupported heading markup")
    return value


class FlashcardV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    front_markdown: str
    back_markdown: str
    hint_markdown: str | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_null_hint(cls, value: Any) -> Any:
        if (
            isinstance(value, dict)
            and "hint_markdown" in value
            and value["hint_markdown"] is None
        ):
            raise ValueError("hint_markdown must be omitted instead of null")
        return value

    @field_validator("front_markdown")
    @classmethod
    def validate_front(cls, value: str) -> str:
        return _validate_markdown(
            value,
            field="front_markdown",
            maximum=FLASHCARDS_MAX_FRONT_CHARS,
        )

    @field_validator("back_markdown")
    @classmethod
    def validate_back(cls, value: str) -> str:
        return _validate_markdown(
            value,
            field="back_markdown",
            maximum=FLASHCARDS_MAX_BACK_CHARS,
        )

    @field_validator("hint_markdown")
    @classmethod
    def validate_hint(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_markdown(
            value,
            field="hint_markdown",
            maximum=FLASHCARDS_MAX_HINT_CHARS,
        )


class FlashcardDeckV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[1]
    title: str
    cards: list[FlashcardV1]

    @field_validator("schema_version", mode="before")
    @classmethod
    def validate_schema_version(cls, value: Any) -> Any:
        if type(value) is not int or value != 1:
            raise ValueError("schema_version must be the integer 1")
        return value

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("title must not be empty")
        if len(value) > FLASHCARDS_MAX_TITLE_CHARS:
            raise ValueError(f"title exceeds {FLASHCARDS_MAX_TITLE_CHARS} characters")
        if "\n" in value or "\r" in value or _CONTROL_RE.search(value):
            raise ValueError("title must be one line without control characters")
        if _RAW_HTML_RE.search(value):
            raise ValueError("title contains unsupported HTML")
        return value

    @field_validator("cards")
    @classmethod
    def validate_cards(cls, value: list[FlashcardV1]) -> list[FlashcardV1]:
        if not FLASHCARDS_MIN_CARDS <= len(value) <= FLASHCARDS_MAX_CARDS:
            raise ValueError(
                "cards must contain between "
                f"{FLASHCARDS_MIN_CARDS} and {FLASHCARDS_MAX_CARDS} entries"
            )

        seen: set[str] = set()
        for card in value:
            normalized = " ".join(
                unicodedata.normalize("NFKC", card.front_markdown).casefold().split()
            )
            if normalized in seen:
                raise ValueError("cards contain duplicate fronts")
            seen.add(normalized)
        return value


def parse_flashcards_deck(data: bytes) -> FlashcardDeckV1:
    """Parse exact UTF-8 JSON into the closed version-one deck model."""
    if not data:
        raise ValueError("flashcard artifact is empty")
    if data.startswith(b"\xef\xbb\xbf"):
        raise ValueError("flashcard artifact must not contain a UTF-8 byte-order mark")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("flashcard artifact must be valid UTF-8") from None
    if not text.strip():
        raise ValueError("flashcard artifact is empty")
    if _CONTROL_RE.search(text):
        raise ValueError("flashcard artifact contains unsupported control characters")

    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(
            f"flashcard artifact is not valid strict JSON: {exc}"
        ) from None

    try:
        return FlashcardDeckV1.model_validate(value)
    except ValidationError as exc:
        findings = []
        for error in exc.errors(include_url=False):
            location = ".".join(str(part) for part in error["loc"]) or "deck"
            findings.append(f"{location}: {error['msg']}")
        raise ValueError("; ".join(findings)) from None


def check_flashcards_json(data: bytes) -> StructuralCheckResult:
    try:
        deck = parse_flashcards_deck(data)
    except ValueError as exc:
        return StructuralCheckResult((str(exc),))
    return StructuralCheckResult(
        (),
        notes=(
            f"Flashcard deck: schema {deck.schema_version}, {len(deck.cards)} cards",
        ),
    )


def flashcards_to_markdown(data: bytes) -> str:
    """Project a verified JSON deck into searchable, readable Markdown."""
    deck = parse_flashcards_deck(data)
    sections = [f"# {deck.title.strip()}"]
    for index, card in enumerate(deck.cards, 1):
        section = [
            f"## Card {index}",
            "### Front",
            card.front_markdown.strip(),
            "### Back",
            card.back_markdown.strip(),
        ]
        if card.hint_markdown is not None:
            section.extend(("### Hint", card.hint_markdown.strip()))
        sections.append("\n\n".join(section))
    return "\n\n".join(sections) + "\n"
