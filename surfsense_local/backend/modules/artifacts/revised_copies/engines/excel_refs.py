"""A1 cell and range references within Excel's grid (XFD1048576)."""

from __future__ import annotations

import re

MAX_COLUMN = 16_384
MAX_ROW = 1_048_576

_CELL = re.compile(r"([A-Za-z]{1,3})([1-9][0-9]{0,6})")


def parse_cell(ref: str) -> tuple[int, int] | None:
    """(column, row), both 1-based; None outside the grid or not a plain ref."""
    match = (
        _CELL.fullmatch(ref.strip().replace("$", "")) if isinstance(ref, str) else None
    )
    if not match:
        return None
    column = 0
    for letter in match.group(1).upper():
        column = column * 26 + ord(letter) - 64
    row = int(match.group(2))
    if column > MAX_COLUMN or row > MAX_ROW:
        return None
    return column, row


def parse_range(ref: str) -> tuple[tuple[int, int], tuple[int, int]] | None:
    """Top-left and bottom-right; a single cell is a one-cell range."""
    if not isinstance(ref, str):
        return None
    ends = ref.strip().split(":")
    if len(ends) > 2:
        return None
    first = parse_cell(ends[0])
    last = parse_cell(ends[-1])
    if first is None or last is None or last[0] < first[0] or last[1] < first[1]:
        return None
    return first, last


def column_letters(column: int) -> str:
    letters = ""
    while column:
        column, remainder = divmod(column - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def cell_name(column: int, row: int) -> str:
    return f"{column_letters(column)}{row}"


def range_name(first: tuple[int, int], last: tuple[int, int]) -> str:
    return f"{cell_name(*first)}:{cell_name(*last)}"


def in_range(
    cell: tuple[int, int], area: tuple[tuple[int, int], tuple[int, int]]
) -> bool:
    (left, top), (right, bottom) = area
    return left <= cell[0] <= right and top <= cell[1] <= bottom
