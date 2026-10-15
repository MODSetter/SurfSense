"""A table an analysis saved, as the model reads it: its size and its first rows and columns in Markdown."""

import csv
from pathlib import Path

ROWS = 20
COLUMNS = 8
CELL_CHARS = 40


def table_preview(path: Path) -> str:
    """`<name>, R rows and C columns:` then the Markdown table, and what was left out.

    Read with the csv module: the API ships no pandas.
    """
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    try:
        with path.open(encoding="utf-8-sig", errors="replace", newline="") as file:
            rows = csv.reader(file, delimiter=delimiter)
            header = next(rows, None)
            if header is None:
                return f"{path.name} is empty."
            shown: list[list[str]] = []
            count = 0
            widest = len(header)
            for row in rows:
                count += 1
                widest = max(widest, len(row))
                if len(shown) < ROWS:
                    shown.append(row)
    except (OSError, csv.Error) as error:
        return f"{path.name} could not be read as a table: {error}"
    columns = min(widest, COLUMNS)
    lines = [
        f"{path.name}, {_count(count, 'row')} and {_count(widest, 'column')}:",
        _line(header, columns),
        "| " + " | ".join(["---"] * columns) + " |",
        *(_line(row, columns) for row in shown),
    ]
    cut = []
    if count > ROWS:
        cut.append(f"{ROWS} rows")
    if widest > COLUMNS:
        cut.append(f"{COLUMNS} columns")
    if cut:
        lines.append(f"First {' and '.join(cut)} shown.")
    return "\n".join(lines)


def _line(row: list[str], columns: int) -> str:
    cells = (row + [""] * columns)[:columns]
    return "| " + " | ".join(_cell(cell) for cell in cells) + " |"


def _cell(text: str) -> str:
    text = " ".join(text.split()).replace("|", "\\|")
    return text if len(text) <= CELL_CHARS else f"{text[: CELL_CHARS - 1]}…"


def _count(n: int, unit: str) -> str:
    return f"{n:,} {unit}" if n == 1 else f"{n:,} {unit}s"
