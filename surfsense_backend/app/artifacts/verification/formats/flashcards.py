"""Strict structural checks and indexing projection for flashcard decks."""

from __future__ import annotations

import json
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

# Published schema versions are immutable read contracts. Add a V2 model/parser
# for incompatible changes instead of tightening V1 in place.
FLASHCARDS_MIN_CARDS = 15
FLASHCARDS_MAX_CARDS = 100
FLASHCARDS_MAX_TITLE_CHARS = 200
FLASHCARDS_MAX_FRONT_CHARS = 4_000
FLASHCARDS_MAX_BACK_CHARS = 12_000
FLASHCARDS_MAX_HINT_CHARS = 2_000

_MARKDOWN_SPECIAL_CHARS = frozenset("\\`*_{}[]<>()#+-.!|>")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"unsupported JSON number: {value}")


def _has_control_character(value: str) -> bool:
    return (
        any(ord(character) < 32 and character not in "\t\n\r" for character in value)
        or "\x7f" in value
    )


def _is_escaped(value: str, index: int) -> bool:
    preceding_backslashes = 0
    index -= 1
    while index >= 0 and value[index] == "\\":
        preceding_backslashes += 1
        index -= 1
    return preceding_backslashes % 2 == 1


def _validate_latex(latex: str, *, field: str) -> None:
    if not latex.strip():
        raise ValueError(f"{field} contains an empty LaTeX expression")

    brace_depth = 0
    for index, character in enumerate(latex):
        if _is_escaped(latex, index):
            continue
        if character == "{":
            brace_depth += 1
        elif character == "}":
            brace_depth -= 1
            if brace_depth < 0:
                break
    if brace_depth != 0:
        raise ValueError(f"{field} contains unbalanced LaTeX braces")


def _split_text_and_latex(
    value: str, *, field: str, maximum: int
) -> list[tuple[Literal["text", "inline", "display"], str]]:
    if not value.strip():
        raise ValueError(f"{field} must not be empty")
    if len(value) > maximum:
        raise ValueError(f"{field} exceeds {maximum} characters")
    if _has_control_character(value):
        raise ValueError(f"{field} contains unsupported control characters")

    segments: list[tuple[Literal["text", "inline", "display"], str]] = []
    text_start = 0
    index = 0
    while index < len(value):
        delimiter = value[index : index + 2]
        if delimiter in {r"\)", r"\]"} and not _is_escaped(value, index):
            raise ValueError(f"{field} contains an unmatched LaTeX delimiter")
        if delimiter not in {r"\(", r"\["} or _is_escaped(value, index):
            index += 1
            continue

        if index > text_start:
            segments.append(("text", value[text_start:index]))
        kind: Literal["inline", "display"] = (
            "inline" if delimiter == r"\(" else "display"
        )
        closing = r"\)" if kind == "inline" else r"\]"
        latex_start = index + 2
        index = latex_start
        while index < len(value):
            candidate = value[index : index + 2]
            if candidate in {r"\(", r"\["} and not _is_escaped(value, index):
                raise ValueError(f"{field} contains nested LaTeX delimiters")
            if candidate in {r"\)", r"\]"} and not _is_escaped(value, index):
                if candidate != closing:
                    raise ValueError(f"{field} contains mismatched LaTeX delimiters")
                latex = value[latex_start:index]
                _validate_latex(latex, field=field)
                segments.append((kind, latex))
                index += 2
                text_start = index
                break
            index += 1
        else:
            raise ValueError(f"{field} contains an unclosed LaTeX delimiter")

    if text_start < len(value):
        segments.append(("text", value[text_start:]))
    return segments


def _validate_text(value: str, *, field: str, maximum: int) -> str:
    _split_text_and_latex(value, field=field, maximum=maximum)
    return value


def _escape_markdown(value: str) -> str:
    return "".join(
        f"\\{character}" if character in _MARKDOWN_SPECIAL_CHARS else character
        for character in value
    )


def _text_to_markdown(value: str, *, field: str, maximum: int) -> str:
    return "".join(
        _escape_markdown(content)
        if kind == "text"
        else f"\\({content}\\)"
        if kind == "inline"
        else f"\\[\n{content}\n\\]"
        for kind, content in _split_text_and_latex(value, field=field, maximum=maximum)
    )


class FlashcardV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    front_text: str
    back_text: str
    hint_text: str | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_null_hint(cls, value: Any) -> Any:
        if (
            isinstance(value, dict)
            and "hint_text" in value
            and value["hint_text"] is None
        ):
            raise ValueError("hint_text must be omitted instead of null")
        return value

    @field_validator("front_text")
    @classmethod
    def validate_front(cls, value: str) -> str:
        return _validate_text(
            value,
            field="front_text",
            maximum=FLASHCARDS_MAX_FRONT_CHARS,
        )

    @field_validator("back_text")
    @classmethod
    def validate_back(cls, value: str) -> str:
        return _validate_text(
            value,
            field="back_text",
            maximum=FLASHCARDS_MAX_BACK_CHARS,
        )

    @field_validator("hint_text")
    @classmethod
    def validate_hint(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_text(
            value,
            field="hint_text",
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
        if "\n" in value or "\r" in value or _has_control_character(value):
            raise ValueError("title must be one line without control characters")
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
                unicodedata.normalize("NFKC", card.front_text).casefold().split()
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
    if _has_control_character(text):
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
    sections = [f"# {_escape_markdown(deck.title.strip())}"]
    for index, card in enumerate(deck.cards, 1):
        section = [
            f"## Card {index}",
            "### Front",
            _text_to_markdown(
                card.front_text.strip(),
                field="front_text",
                maximum=FLASHCARDS_MAX_FRONT_CHARS,
            ),
            "### Back",
            _text_to_markdown(
                card.back_text.strip(),
                field="back_text",
                maximum=FLASHCARDS_MAX_BACK_CHARS,
            ),
        ]
        if card.hint_text is not None:
            section.extend(
                (
                    "### Hint",
                    _text_to_markdown(
                        card.hint_text.strip(),
                        field="hint_text",
                        maximum=FLASHCARDS_MAX_HINT_CHARS,
                    ),
                )
            )
        sections.append("\n\n".join(section))
    return "\n\n".join(sections) + "\n"
