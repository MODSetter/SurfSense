"""A contract as the Word engine reads it: each paragraph with the text an edit may quote, and the list
number Word shows beside it, which is not in that text."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from modules.artifacts.revised_copies.engines.package import Package, open_package
from modules.artifacts.revised_copies.engines.word import main_part
from modules.artifacts.revised_copies.engines.word_text import paragraphs
from modules.artifacts.revised_copies.engines.word_xml import REL, STYLES_REL, w
from worker.ingestion.word_markdown.list_level import list_level
from worker.ingestion.word_markdown.numbering import ListNumbering
from worker.ingestion.word_markdown.styles import ParagraphStyles

NUMBERING_REL = f"{REL}/numbering"
_CELL = w("tc")


@dataclass(frozen=True)
class Clause:
    id: str  # "P<n>": the model's name for it, counting paragraphs that hold text
    text: str  # as the engine reads it now; every quote is matched against this
    label: str  # the list number Word shows, "" for none
    heading: bool
    in_table: bool
    # Positions in `text` inside a field, which no edit may touch.
    in_field: frozenset[int]


@dataclass(frozen=True)
class Contract:
    clauses: tuple[Clause, ...]

    def find(self, clause_id: str) -> int | None:
        """The index of the clause the model named, or None for an id the contract lacks."""
        for index, clause in enumerate(self.clauses):
            if clause.id == clause_id:
                return index
        return None


def read_contract(path: Path) -> Contract:
    package = open_package(path)
    main = main_part(package)
    body = package.xml(main).find(w("body"))
    styles = ParagraphStyles(_related_root(package, main, STYLES_REL))
    numbering = ListNumbering(
        _related_root(package, main, NUMBERING_REL), styles.numbering_style_num
    )
    clauses: list[Clause] = []
    for paragraph in paragraphs(body):
        style_id, numbered = list_level(paragraph.element, styles, numbering)
        # Counted even when empty: Word numbers an empty list paragraph too.
        marker = numbering.next_marker(*numbered) if numbered else None
        if not paragraph.text.strip():
            continue
        clauses.append(
            Clause(
                id=f"P{len(clauses) + 1}",
                text=paragraph.text,
                label=marker or "",
                heading=styles.role(style_id).kind != "text",
                in_table=any(a.tag == _CELL for a in paragraph.element.iterancestors()),
                in_field=frozenset(
                    position
                    for position, (first, last) in enumerate(paragraph.spans)
                    if any(a.in_field for a in paragraph.atoms[first : last + 1])
                ),
            )
        )
    return Contract(tuple(clauses))


def _related_root(package: Package, main: str, relationship: str):
    names = [n for n in package.related(main, relationship) if n in package.names]
    return package.xml(names[0]) if names else None
