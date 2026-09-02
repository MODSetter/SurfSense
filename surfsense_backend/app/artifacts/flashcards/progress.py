"""Bounded, generation-scoped flashcard study state stored per user."""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

FlashcardMark = Literal["good", "again"]
FlashcardIndex = Annotated[int, Field(strict=True, ge=0)]


class FlashcardProgressUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    generation: int = Field(gt=0)
    card_index: int = Field(ge=0)
    mark: FlashcardMark | None


class FlashcardOrderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    generation: int = Field(gt=0)
    order: list[FlashcardIndex] = Field(min_length=1, max_length=100)


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

    marks: dict[str, FlashcardMark] = {}
    for index in range(max(0, card_count)):
        mark = raw_marks.get(str(index))
        if mark in ("good", "again"):
            marks[str(index)] = mark
    return {"generation": generation, "marks": marks, "order": list(raw_order)}


def _study_by_user(
    metadata: dict[str, Any] | None,
    *,
    generation: int,
    card_count: int,
) -> dict[str, dict[str, object]]:
    flashcards = metadata.get("flashcards") if isinstance(metadata, dict) else None
    raw_users = (
        flashcards.get("study_by_user") if isinstance(flashcards, dict) else None
    )
    if not isinstance(raw_users, dict):
        return {}

    users: dict[str, dict[str, object]] = {}
    for user_key, raw_state in raw_users.items():
        if not isinstance(user_key, str):
            continue
        try:
            if str(UUID(user_key)) != user_key:
                continue
        except ValueError:
            continue
        state = _valid_state(
            raw_state,
            generation=generation,
            card_count=card_count,
        )
        if state is not None:
            users[user_key] = state
    return users


def sanitize_flashcard_study_state(
    metadata: dict[str, Any] | None,
    *,
    user_id: UUID,
    generation: int,
    card_count: int,
) -> dict[str, object]:
    """Return only one user's valid state for the current verified deck."""
    state = _study_by_user(
        metadata,
        generation=generation,
        card_count=card_count,
    ).get(str(user_id))
    return state or {
        "generation": generation,
        "marks": {},
        "order": _canonical_order(card_count),
    }


def study_state_digest(state: dict[str, object]) -> str:
    canonical = json.dumps(
        state,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(canonical).hexdigest()[:16]


def apply_flashcard_mark(
    metadata: dict[str, Any] | None,
    *,
    user_id: UUID,
    generation: int,
    card_count: int,
    card_index: int,
    mark: FlashcardMark | None,
) -> tuple[dict[str, Any], dict[str, object]]:
    if not 0 <= card_index < card_count:
        raise ValueError("card_index is outside the current flashcard deck")

    users = _study_by_user(
        metadata,
        generation=generation,
        card_count=card_count,
    )
    state = users.get(str(user_id)) or {
        "generation": generation,
        "marks": {},
        "order": _canonical_order(card_count),
    }
    marks = dict(state["marks"])
    key = str(card_index)
    if mark is None:
        marks.pop(key, None)
    else:
        marks[key] = mark
    state = {**state, "marks": marks}
    users[str(user_id)] = state
    return _with_users(metadata, users), state


def reset_flashcard_progress(
    metadata: dict[str, Any] | None,
    *,
    user_id: UUID,
    generation: int,
    card_count: int,
) -> tuple[dict[str, Any], dict[str, object]]:
    users = _study_by_user(
        metadata,
        generation=generation,
        card_count=card_count,
    )
    user_key = str(user_id)
    state = users.get(user_key) or {
        "generation": generation,
        "marks": {},
        "order": _canonical_order(card_count),
    }
    state = {**state, "marks": {}}
    if state["order"] == _canonical_order(card_count):
        users.pop(user_key, None)
    else:
        users[user_key] = state
    return _with_users(metadata, users), state


def apply_flashcard_order(
    metadata: dict[str, Any] | None,
    *,
    user_id: UUID,
    generation: int,
    card_count: int,
    order: list[int],
) -> tuple[dict[str, Any], dict[str, object]]:
    if (
        len(order) != card_count
        or any(type(index) is not int for index in order)
        or sorted(order) != _canonical_order(card_count)
    ):
        raise ValueError("order must contain every flashcard index exactly once")
    users = _study_by_user(
        metadata,
        generation=generation,
        card_count=card_count,
    )
    user_key = str(user_id)
    state = users.get(user_key) or {
        "generation": generation,
        "marks": {},
        "order": _canonical_order(card_count),
    }
    state = {**state, "order": list(order)}
    users[user_key] = state
    return _with_users(metadata, users), state


def _with_users(
    metadata: dict[str, Any] | None,
    users: dict[str, dict[str, object]],
) -> dict[str, Any]:
    updated = dict(metadata) if isinstance(metadata, dict) else {}
    if users:
        updated["flashcards"] = {"study_by_user": users}
    else:
        updated.pop("flashcards", None)
    return updated
