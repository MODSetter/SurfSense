"""Bounded, generation-scoped flashcard study state — the same shape as
quiz_progress.py, ported from surfsense_web's per-user study store minus the
per-user layer (see quiz_progress.py's module docstring for why).
"""

from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import HTTPException, status

from modules.artifacts.models import Artifact, ArtifactFileRole
from shared.config import get_storage_settings

FlashcardMark = Literal["good", "again"]


def read_flashcard_count(artifact: Artifact) -> int:
    """How many cards the deck has, for bounds-checking and order validation."""
    file = next(
        (f for f in artifact.files if f.role is ArtifactFileRole.PRIMARY), None
    )
    if file is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "deck has no file yet")
    path = get_storage_settings().data_dir / file.storage_key
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "the deck file is no longer readable"
        ) from error
    cards = data.get("cards")
    if not isinstance(cards, list):
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "malformed deck")
    return len(cards)


def _canonical_order(card_count: int) -> list[int]:
    return list(range(max(0, card_count)))


def _valid_state(
    value: object, *, generation: int, card_count: int
) -> dict[str, object] | None:
    if not isinstance(value, dict) or type(value.get("generation")) is not int:
        return None
    if value["generation"] != generation:
        return None
    raw_marks = value.get("marks")
    raw_order = value.get("order")
    if not isinstance(raw_marks, dict) or not isinstance(raw_order, list):
        return None
    if (
        len(raw_order) != card_count
        or any(type(index) is not int for index in raw_order)
        or sorted(raw_order) != _canonical_order(card_count)
    ):
        return None

    marks: dict[str, str] = {}
    for index in range(card_count):
        mark = raw_marks.get(str(index))
        if mark in ("good", "again"):
            marks[str(index)] = mark
    return {"generation": generation, "marks": marks, "order": list(raw_order)}


def empty_flashcard_state(*, generation: int, card_count: int) -> dict[str, object]:
    return {
        "generation": generation,
        "marks": {},
        "order": _canonical_order(card_count),
    }


def sanitize_flashcard_state(
    metadata: dict[str, Any] | None, *, generation: int, card_count: int
) -> dict[str, object]:
    state = _valid_state(
        (metadata or {}).get("flashcard_state"),
        generation=generation,
        card_count=card_count,
    )
    return state or empty_flashcard_state(generation=generation, card_count=card_count)


def _with_state(
    metadata: dict[str, Any] | None, state: dict[str, object]
) -> dict[str, Any]:
    updated = dict(metadata) if isinstance(metadata, dict) else {}
    updated["flashcard_state"] = state
    return updated


def apply_flashcard_mark(
    metadata: dict[str, Any] | None,
    *,
    generation: int,
    card_count: int,
    card_index: int,
    mark: FlashcardMark | None,
) -> tuple[dict[str, Any], dict[str, object]]:
    if not 0 <= card_index < card_count:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "card_index is outside the current deck"
        )
    state = sanitize_flashcard_state(
        metadata, generation=generation, card_count=card_count
    )
    marks = dict(state["marks"])
    key = str(card_index)
    if mark is None:
        marks.pop(key, None)
    else:
        marks[key] = mark
    state = {**state, "marks": marks}
    return _with_state(metadata, state), state


def reset_flashcard_progress(
    metadata: dict[str, Any] | None, *, generation: int, card_count: int
) -> tuple[dict[str, Any], dict[str, object]]:
    state = sanitize_flashcard_state(
        metadata, generation=generation, card_count=card_count
    )
    state = {**state, "marks": {}}
    return _with_state(metadata, state), state


def apply_flashcard_order(
    metadata: dict[str, Any] | None,
    *,
    generation: int,
    card_count: int,
    order: list[int],
) -> tuple[dict[str, Any], dict[str, object]]:
    if (
        len(order) != card_count
        or any(type(index) is not int for index in order)
        or sorted(order) != _canonical_order(card_count)
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "order must contain every flashcard index exactly once",
        )
    state = sanitize_flashcard_state(
        metadata, generation=generation, card_count=card_count
    )
    state = {**state, "order": list(order)}
    return _with_state(metadata, state), state
