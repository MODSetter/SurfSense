"""The value an answer is written as: the requester's own dropdown spelling, or none when their list lacks it."""

from __future__ import annotations

from modules.jobs.workbook_rows.config import AnswerChoice


def cell_value(choice: AnswerChoice, allowed: tuple[str, ...] | None) -> str | None:
    """None means the cell stays blank: the dropdown offers nothing that means this answer."""
    if allowed is None:
        return choice.cell_values[0]
    by_folded = {value.strip().casefold(): value for value in allowed}
    for spelling in (choice.answer, *choice.cell_values):
        found = by_folded.get(spelling.strip().casefold())
        if found is not None:
            return found
    return None
