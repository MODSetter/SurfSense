"""A Word file the agent made, read the way a live case checks it: blocks in order, headings, tables, pictures."""

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass
from functools import cached_property
from typing import Literal

import docx
from docx.document import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

# "1.", "2.3", "IV)", "A." at the start of a heading's text.
_NUMBERED_TEXT = re.compile(r"\s*(\d+(\.\d+)*|[IVXLC]+|[A-Z])[.)]?\s")
_HEADING_STYLE = re.compile(r"Heading (\d)")


@dataclass(frozen=True)
class Block:
    kind: Literal["title", "heading", "paragraph", "table"]
    text: str
    level: int = 0
    numbered: bool = False


class WordFile:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.document: Document = docx.Document(io.BytesIO(data))

    @cached_property
    def blocks(self) -> list[Block]:
        """The body's non-empty paragraphs and its tables, top to bottom."""
        found: list[Block] = []
        for item in self.document.iter_inner_content():
            if isinstance(item, Table):
                found.append(Block("table", _table_text(item)))
                continue
            if not item.text.strip() and not _has_picture(item):
                continue
            level = _heading_level(item)
            if level == 0:
                found.append(Block("title", item.text))
            elif level is not None:
                found.append(Block("heading", item.text, level, _is_numbered(item)))
            else:
                found.append(Block("paragraph", item.text))
        return found

    @property
    def headings(self) -> list[Block]:
        return [b for b in self.blocks if b.kind == "heading"]

    @property
    def paragraphs(self) -> list[str]:
        return [b.text for b in self.blocks if b.kind == "paragraph" and b.text.strip()]

    @property
    def tables(self) -> list[list[list[str]]]:
        return [
            [[cell.text for cell in row.cells] for row in table.rows]
            for table in self.document.tables
        ]

    @property
    def text(self) -> str:
        return "\n".join(b.text for b in self.blocks)

    @cached_property
    def pictures(self) -> set[str]:
        """The hash of every picture the file holds."""
        with zipfile.ZipFile(io.BytesIO(self.data)) as package:
            return {
                hashlib.sha256(package.read(name)).hexdigest()
                for name in package.namelist()
                if name.startswith("word/media/")
            }


def _table_text(table: Table) -> str:
    return "\n".join(" | ".join(c.text for c in row.cells) for row in table.rows)


def _has_picture(paragraph: Paragraph) -> bool:
    return bool(paragraph._p.xpath(".//w:drawing"))


def _styles(paragraph: Paragraph):
    style = paragraph.style
    while style is not None:
        yield style
        style = style.base_style


def _heading_level(paragraph: Paragraph) -> int | None:
    """0 for the title, n for Heading n, None for body text."""
    for style in _styles(paragraph):
        if style.name == "Title":
            return 0
        match = _HEADING_STYLE.fullmatch(style.name or "")
        if match:
            return int(match[1])
    return None


def _is_numbered(paragraph: Paragraph) -> bool:
    if _NUMBERED_TEXT.match(paragraph.text):
        return True
    if paragraph._p.xpath("./w:pPr/w:numPr"):
        return True
    return any(style.element.xpath("./w:pPr/w:numPr") for style in _styles(paragraph))
