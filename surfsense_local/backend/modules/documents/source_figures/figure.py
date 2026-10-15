"""A kept figure as a document script asks for it: by name, `<document id>-<n>`."""

import re
from dataclasses import dataclass
from typing import Any

# ASCII digits only: \d and int() also take other scripts' digits.
_NAME = re.compile(r"([0-9]{1,18})-([1-9][0-9]{0,8})")


@dataclass(frozen=True)
class SourceFigure:
    name: str
    document_id: int
    caption: str | None
    page: int | None
    width: int
    height: int


def figure_name(document_id: int, n: int) -> str:
    return f"{document_id}-{n}"


def parse_figure_name(name: str) -> tuple[int, int] | None:
    """The document id and figure number a name holds, or None for any other text."""
    match = _NAME.fullmatch(name)
    return (int(match[1]), int(match[2])) if match else None


def from_index_entry(document_id: int, entry: dict[str, Any]) -> SourceFigure:
    # Named from the document, not from the index: the folder is keyed by its id.
    return SourceFigure(
        name=figure_name(document_id, entry["n"]),
        document_id=document_id,
        caption=entry.get("caption"),
        page=entry.get("page"),
        width=entry["width"],
        height=entry["height"],
    )
