"""Footnotes and endnotes, labelled in the order the text cites them, as Word
numbers them by default: footnotes 1, 2, 3; endnotes i, ii, iii."""

from typing import Any, NamedTuple

from worker.ingestion.word_markdown.number_formats import formatted
from worker.ingestion.word_markdown.ooxml_names import w

_ID = w("id")
_NOTE_TAGS = {"footnote": w("footnote"), "endnote": w("endnote")}
_NOTE_FORMATS = {"footnote": "decimal", "endnote": "lowerRoman"}


class CitedNote(NamedTuple):
    label: str
    element: Any
    part: Any  # whose relationships its links resolve against


class Notes:
    def __init__(self, parts: dict[str, tuple[Any, Any] | None]) -> None:
        self._notes: dict[str, dict[str, tuple[Any, Any]]] = {}
        for kind, found in parts.items():
            root, part = found if found is not None else (None, None)
            self._notes[kind] = (
                {}
                if root is None
                else {
                    note.get(_ID, ""): (note, part)
                    for note in root.iterchildren(_NOTE_TAGS[kind])
                }
            )
        self._labels: dict[tuple[str, str], str] = {}
        self._cited_of_kind: dict[str, int] = {}
        self.cited: list[CitedNote] = []

    def mark(self, kind: str, note_id: str) -> str:
        """The citation's markdown mark, [^1]; "" when the note is missing."""
        key = (kind, note_id)
        if key not in self._labels:
            found = self._notes.get(kind, {}).get(note_id)
            if found is None:
                return ""
            count = self._cited_of_kind.get(kind, 0) + 1
            self._cited_of_kind[kind] = count
            label = formatted(count, _NOTE_FORMATS[kind])
            self._labels[key] = label
            self.cited.append(CitedNote(label, *found))
        return f"[^{self._labels[key]}]"
