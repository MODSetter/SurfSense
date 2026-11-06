"""A .docx as markdown, read without Docling: the body in order, then its notes.

Headers, footers and comments are left out, as Docling's markdown leaves them.
"""

import re
from pathlib import Path
from typing import Any, NamedTuple
from urllib.parse import urlsplit

import docx
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml.parser import parse_xml

from worker.ingestion.word_markdown.alternate_content import shown_alternative
from worker.ingestion.word_markdown.inline import (
    inline_text,
    shape_text,
    textboxes_in,
)
from worker.ingestion.word_markdown.list_level import list_level
from worker.ingestion.word_markdown.notes import Notes
from worker.ingestion.word_markdown.numbering import BULLET, ListNumbering
from worker.ingestion.word_markdown.ooxml_names import (
    BODY,
    CUSTOM_XML,
    MC_ALTERNATE_CONTENT,
    SDT,
    SDT_CONTENT,
    TBL,
    P,
)
from worker.ingestion.word_markdown.styles import ParagraphStyles
from worker.ingestion.word_markdown.tables import (
    cells_of,
    grid_columns,
    markdown_table,
    rows_of,
)

_ORDERED_MARKER = re.compile(r"\d{1,9}\.")  # CommonMark's longest list number
_LIST_INDENT = "    "
_MOST_HASHES = 6
# A link elsewhere in the file, or to a path on its author's disk, keeps only its words.
_LINK_SCHEMES = frozenset({"http", "https", "mailto", "ftp"})


class _Block(NamedTuple):
    kind: str  # "text", "heading", "list", "table" or "note"
    text: str
    depth: int = 0  # a list item's w:ilvl


def markdown_of(path: Path) -> str:
    part = docx.Document(str(path)).part
    body = part.element.find(BODY)
    if body is None:
        raise ValueError("the main document part has no w:body")
    styles = ParagraphStyles(_related_root(part, RT.STYLES))
    numbering = ListNumbering(
        _related_root(part, RT.NUMBERING), styles.numbering_style_num
    )
    notes = Notes(
        {
            "footnote": _related(part, RT.FOOTNOTES),
            "endnote": _related(part, RT.ENDNOTES),
        }
    )
    return _joined(_Reader(part, styles, numbering, notes).read(body))


class _Reader:
    def __init__(
        self,
        part: Any,
        styles: ParagraphStyles,
        numbering: ListNumbering,
        notes: Notes,
    ) -> None:
        self._links_part = part
        self._styles = styles
        self._numbering = numbering
        self._notes = notes

    def read(self, body: Any) -> list[_Block]:
        blocks: list[_Block] = []
        self._walk(body, blocks, in_cell=False)
        n = 0
        while n < len(self._notes.cited):  # a note can cite another
            note = self._notes.cited[n]
            n += 1
            self._links_part = note.part
            text = self._flat(note.element)
            if text:
                blocks.append(_Block("note", f"[^{note.label}]: {text}"))
        return blocks

    def _walk(self, container: Any, out: list[_Block], in_cell: bool) -> None:
        for child in container.iterchildren():
            tag = child.tag
            if tag == P:
                self._paragraph(child, out, in_cell)
            elif tag == TBL:
                self._table(child, out, in_cell)
            elif tag == SDT:
                content = child.find(SDT_CONTENT)
                if content is not None:
                    self._walk(content, out, in_cell)
            elif tag == CUSTOM_XML:
                self._walk(child, out, in_cell)
            elif tag == MC_ALTERNATE_CONTENT:
                shown = shown_alternative(child)
                if shown is not None:
                    self._walk(shown, out, in_cell)

    def _paragraph(self, paragraph: Any, out: list[_Block], in_cell: bool) -> None:
        # A text box's words come before its anchor paragraph's, as in Docling.
        boxes = textboxes_in(paragraph)
        for box in boxes:
            self._walk(box, out, in_cell)
        if not boxes and (drawn := shape_text(paragraph)):
            out.append(_Block("text", drawn))

        text = inline_text(paragraph, self._link_target, self._notes.mark)
        style_id, numbered = list_level(paragraph, self._styles, self._numbering)
        role = self._styles.role(style_id)
        # Counted even when empty: Word numbers an empty list paragraph too.
        marker = self._numbering.next_marker(*numbered) if numbered else None
        if not text:
            return

        if role.kind == "text":
            # A numbered heading stays a heading: Docling, blind to numbering a
            # style inherits, reads "Level 2 Bold Heading" clauses as headings.
            if marker is None:
                out.append(_Block("text", text))
            else:
                out.append(_list_item(marker, text, numbered[1]))
            return
        line = text.replace("\n", " ")
        if marker and marker != BULLET:
            line = f"{marker} {line}"
        if not in_cell:  # markdown has no headings inside a table
            hashes = 1 if role.kind == "title" else min(role.level + 1, _MOST_HASHES)
            line = f"{'#' * hashes} {line}"
        out.append(_Block("heading", line))

    def _table(self, table: Any, out: list[_Block], in_cell: bool) -> None:
        rows = rows_of(table)
        if len(rows) == 1 and grid_columns(table) == 1:
            # Docling reads a one-cell table, a framed box, as body text.
            for cell in cells_of(rows[0]):
                self._walk(cell, out, in_cell)
            return
        if in_cell:
            # A table inside a cell flattens into that cell's text.
            texts = (self._flat(cell) for row in rows for cell in cells_of(row))
            flat = " ".join(text for text in texts if text)
            if flat:
                out.append(_Block("text", flat))
            return
        markdown = markdown_table(table, self._flat)
        if markdown:
            out.append(_Block("table", markdown))

    def _flat(self, container: Any) -> str:
        """The container's blocks on one line, as a table cell holds them."""
        inner: list[_Block] = []
        self._walk(container, inner, in_cell=True)
        return " ".join(block.text.replace("\n", " ") for block in inner)

    def _link_target(self, r_id: str) -> str | None:
        relationship = self._links_part.rels.get(r_id)
        address = None if relationship is None else relationship.target_ref
        if not address or urlsplit(address).scheme.lower() not in _LINK_SCHEMES:
            return None
        return address


def _list_item(marker: str, text: str, ilvl: int) -> _Block:
    if marker in ("", BULLET):
        return _Block("list", f"- {text}", ilvl)
    if _ORDERED_MARKER.fullmatch(marker):
        return _Block("list", f"{marker} {text}", ilvl)
    # "1.2." or "(a)" is no markdown list marker: a bullet carries it.
    return _Block("list", f"- {marker} {text}", ilvl)


def _joined(blocks: list[_Block]) -> str:
    """Blocks a blank line apart; a list's items one per line, nested by level."""
    parts: list[str] = []
    previous = None
    base = 0
    for block in blocks:
        text = block.text
        if block.kind == "list":
            # Nested from the shallowest level the list has shown so far.
            base = block.depth if previous != "list" else min(base, block.depth)
            text = _LIST_INDENT * (block.depth - base) + text
        if parts:
            parts.append("\n" if block.kind == previous == "list" else "\n\n")
        parts.append(text)
        previous = block.kind
    return "".join(parts)


def _related(part: Any, relationship_type: str) -> tuple[Any, Any] | None:
    """The XML root of the part this one relates to by that type, and the part."""
    for relationship in part.rels.values():
        if relationship.reltype != relationship_type or relationship.is_external:
            continue
        target = relationship.target_part
        root = getattr(target, "element", None)
        return (parse_xml(target.blob) if root is None else root), target
    return None


def _related_root(part: Any, relationship_type: str) -> Any | None:
    found = _related(part, relationship_type)
    return None if found is None else found[0]
