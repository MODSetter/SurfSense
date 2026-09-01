"""Bounded, generation-scoped flashcard progress stored in artifact metadata."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

FlashcardMark = Literal["good", "again"]


class FlashcardProgressUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    generation: int = Field(gt=0)
    card_index: int = Field(ge=0)
    mark: FlashcardMark | None


def sanitize_flashcard_progress(
    metadata: dict[str, Any] | None,
    *,
    generation: int,
    card_count: int,
) -> dict[str, object]:
    """Return only valid current-generation marks within the verified deck."""
    marks: dict[str, FlashcardMark] = {}
    flashcards = metadata.get("flashcards") if isinstance(metadata, dict) else None
    progress = flashcards.get("progress") if isinstance(flashcards, dict) else None
    raw_marks = progress.get("marks") if isinstance(progress, dict) else None
    if (
        isinstance(progress, dict)
        and type(progress.get("generation")) is int
        and progress["generation"] == generation
        and isinstance(raw_marks, dict)
    ):
        for index in range(max(0, card_count)):
            mark = raw_marks.get(str(index))
            if mark in ("good", "again"):
                marks[str(index)] = mark
    return {"generation": generation, "marks": marks}


def progress_digest(progress: dict[str, object]) -> str:
    canonical = json.dumps(
        progress,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(canonical).hexdigest()[:16]


def apply_flashcard_mark(
    metadata: dict[str, Any] | None,
    *,
    generation: int,
    card_count: int,
    card_index: int,
    mark: FlashcardMark | None,
) -> tuple[dict[str, Any], dict[str, object]]:
    if not 0 <= card_index < card_count:
        raise ValueError("card_index is outside the current flashcard deck")

    progress = sanitize_flashcard_progress(
        metadata,
        generation=generation,
        card_count=card_count,
    )
    marks = dict(progress["marks"])
    key = str(card_index)
    if mark is None:
        marks.pop(key, None)
    else:
        marks[key] = mark
    progress = {"generation": generation, "marks": marks}

    updated = dict(metadata) if isinstance(metadata, dict) else {}
    flashcards = updated.get("flashcards")
    flashcards = dict(flashcards) if isinstance(flashcards, dict) else {}
    flashcards["progress"] = progress
    updated["flashcards"] = flashcards
    return updated, progress
