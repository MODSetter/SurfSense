"""Edits a copy of a PowerPoint deck: text replaced in place, slides deleted or
duplicated. Slide numbers are the deck as sent, before this call's operations."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from modules.artifacts.revised_copies.engines.package import open_package
from modules.artifacts.revised_copies.engines.powerpoint_slides import Deck
from modules.artifacts.revised_copies.engines.powerpoint_text import find, replace
from modules.artifacts.revised_copies.engines.report import (
    Notice,
    OpOutcome,
    Report,
    applied,
    bad_operation,
    nothing_changed,
    op_name,
    refused,
    skip_others,
    unsupported,
)

FORMAT = "pptx"
OPERATIONS = ("replace_text", "delete_slide", "duplicate_slide")
_OTHER_FORMATS = (
    "insert_paragraphs",
    "delete_paragraphs",
    "add_comment",
    "set_cell",
    "set_range",
)
# XML 1.0 cannot carry these; tab, newline and the vertical tab PowerPoint uses for line breaks are allowed.
_XML_INVALID = re.compile("[\x00-\x08\x0c\x0e-\x1f￾￿]")


class _RefusedError(Exception):
    def __init__(self, outcome: OpOutcome):
        self.outcome = outcome


def apply(
    original: Path,
    operations: list[dict[str, Any]],
    out: Path,
    *,
    partial: bool = False,
    **_: Any,
) -> Report:
    input_sha = hashlib.sha256(original.read_bytes()).hexdigest()
    deck = Deck(open_package(original))
    outcomes: list[OpOutcome] = []
    notices: list[Notice] = []
    changed = False

    for index, operation in enumerate(operations):
        try:
            did_change, notice = _apply_one(deck, index, operation)
        except _RefusedError as refusal:
            outcomes.append(refusal.outcome)
            if not partial:
                return Report(
                    False, skip_others(operations, refusal.outcome), (), input_sha, None
                )
            continue
        changed = changed or did_change
        if notice is not None:
            notices.append(notice)
        outcomes.append(applied(index, op_name(operation)))

    if not changed:
        return Report(False, tuple(outcomes), (nothing_changed(),), input_sha, None)
    deck.package.save(out)
    output_sha = hashlib.sha256(out.read_bytes()).hexdigest()
    return Report(True, tuple(outcomes), tuple(notices), input_sha, output_sha)


def _apply_one(deck: Deck, index: int, operation: object) -> tuple[bool, Notice | None]:
    op = op_name(operation)
    if not isinstance(operation, dict) or op == "?":
        raise _RefusedError(
            bad_operation(
                index, op, "op", "each operation is an object with an op name."
            )
        )
    if op in _OTHER_FORMATS:
        raise _RefusedError(unsupported(index, op, FORMAT))
    if op not in OPERATIONS:
        raise _RefusedError(
            bad_operation(index, op, "op", f"use one of {', '.join(OPERATIONS)}.")
        )
    number = operation.get("slide")
    if isinstance(number, bool) or not isinstance(number, int):
        raise _RefusedError(
            bad_operation(index, op, "slide", "the slide's number, counting from 1.")
        )

    if op == "replace_text":
        return _replace_text(deck, index, op, number, operation)
    _slide(deck, index, op, number)
    if op == "delete_slide":
        if deck.remaining <= 1:
            raise _RefusedError(
                refused(
                    index,
                    op,
                    "LAST_SLIDE",
                    {"slide": number},
                    "A deck keeps at least one slide.",
                )
            )
        deck.delete(number)
    else:
        deck.duplicate(number)
    return True, None


def _replace_text(
    deck: Deck, index: int, op: str, number: int, operation: dict
) -> tuple[bool, Notice | None]:
    quote, text, where = (
        operation.get("quote"),
        operation.get("text"),
        operation.get("where", "slide"),
    )
    if not isinstance(quote, str) or not quote.strip():
        raise _RefusedError(
            bad_operation(
                index,
                op,
                "quote",
                "quote the words to replace, as they read on the slide.",
            )
        )
    if not isinstance(text, str):
        raise _RefusedError(
            bad_operation(
                index, op, "text", "the new words; an empty text deletes the quote."
            )
        )
    if _XML_INVALID.search(text):
        raise _RefusedError(
            bad_operation(index, op, "text", "control characters cannot go on a slide.")
        )
    if where not in ("slide", "notes"):
        raise _RefusedError(bad_operation(index, op, "where", "slide or notes."))
    part = _slide(deck, index, op, number)
    if where == "notes":
        part = deck.notes_part(part)
        if part is None:
            raise _RefusedError(
                refused(
                    index,
                    op,
                    "NOTES_MISSING",
                    {"slide": number},
                    f"Slide {number} has no speaker notes.",
                )
            )
    search = find(deck.xml(part), quote)
    if search.crosses_paragraphs:
        raise _RefusedError(
            refused(
                index,
                op,
                "QUOTE_CROSSES_PARAGRAPHS",
                {"quote": quote},
                "The quote runs across paragraphs; replace each paragraph's part separately.",
            )
        )
    if not search.matches:
        place = f"slide {number}'s notes" if where == "notes" else f"slide {number}"
        raise _RefusedError(
            refused(
                index,
                op,
                "QUOTE_NOT_FOUND",
                {"quote": quote},
                f"The quote is not on {place}; quote the words exactly as they read.",
            )
        )
    if len(search.matches) > 1:
        count = len(search.matches)
        raise _RefusedError(
            refused(
                index,
                op,
                "QUOTE_AMBIGUOUS",
                {"quote": quote, "count": count},
                f"The quote occurs {count} times there; quote more words so it occurs once.",
            )
        )
    match = search.matches[0]
    if match.in_field:
        raise _RefusedError(
            refused(
                index,
                op,
                "QUOTE_IN_FIELD",
                {"quote": quote},
                "The quote includes a field such as a slide number or date, which PowerPoint fills in.",
            )
        )
    merged = match.merges_formatting
    if not merged and match.text == text:
        return False, None
    replace(match, text)
    deck.save_xml(part)
    if not merged:
        return True, None
    return True, Notice(
        "RUN_FORMATTING_MERGED",
        {"slide": number, "quote": quote},
        f'The replacement for "{quote}" on slide {number} took the formatting of its first words; '
        "the quote spanned differently formatted text.",
    )


def _slide(deck: Deck, index: int, op: str, number: int) -> str:
    part = deck.slide_part(number)
    if part is None:
        why = (
            f"Slide {number} was deleted earlier in this call."
            if deck.is_deleted(number)
            else f"The deck has {deck.count} slides; number them from 1 as sent."
        )
        raise _RefusedError(
            refused(
                index,
                op,
                "SLIDE_NOT_FOUND",
                {"slide": number, "count": deck.count},
                why,
            )
        )
    return part
