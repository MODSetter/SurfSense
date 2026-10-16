"""What a paragraph style makes of its paragraphs: a title, a heading level, a list.

Headings follow Docling's msword reader (2.125), so a file keeps the outline it
had: the style id or name says "heading", its own w:outlineLvl wins, and an
outline level alone makes a heading unless the style is a title. Numbering
follows Word: inherited along w:basedOn, which Docling does not walk.
"""

import re
from functools import cache
from typing import Any, NamedTuple

from worker.ingestion.word_markdown.ooxml_names import (
    ILVL,
    NUM_ID,
    NUM_PR,
    OUTLINE_LVL,
    P_PR,
    VAL,
    w,
)

_STYLE = w("style")
_TYPE = w("type")
_STYLE_ID = w("styleId")
_DEFAULT = w("default")
_NAME = w("name")
_BASED_ON = w("basedOn")
_ON = frozenset({"1", "true", "on"})
_CHAIN_LIMIT = 10
_NAME_AND_NUMBER = re.compile(r"(\D+)(\d+)$|^(\d+)(\D+)")


class Role(NamedTuple):
    kind: str  # "title", "heading" or "text"
    level: int  # a heading's level, 1-based; 0 otherwise


TEXT = Role("text", 0)


class StyleNumbering(NamedTuple):
    num_id: str | None
    ilvl: int | None


class ParagraphStyles:
    def __init__(self, root: Any | None) -> None:
        self._by_id: dict[str, Any] = {}
        self._default: Any | None = None  # the last default, as python-docx takes it
        self.role = cache(self._role)
        self.numbering = cache(self._numbering)
        for style in [] if root is None else root.iterchildren(_STYLE):
            style_id = style.get(_STYLE_ID)
            if style_id is not None:
                self._by_id.setdefault(style_id, style)
            if style.get(_TYPE) == "paragraph" and style.get(_DEFAULT) in _ON:
                self._default = style

    def resolved_id(self, style_id: str | None) -> str | None:
        """The paragraph style a w:pStyle means: the default one when it names none."""
        style = self._paragraph_style(style_id)
        return None if style is None else style.get(_STYLE_ID)

    def numbering_style_num(self, style_id: str) -> str | None:
        """The w:num a numbering style points at, for w:numStyleLink."""
        style = self._by_id.get(style_id)
        num_pr = None if style is None else style.find(f"{P_PR}/{NUM_PR}")
        num_id = None if num_pr is None else num_pr.find(NUM_ID)
        return None if num_id is None else num_id.get(VAL)

    def _paragraph_style(self, style_id: str | None) -> Any | None:
        style = self._by_id.get(style_id) if style_id else None
        if style is None or style.get(_TYPE) != "paragraph":
            return self._default
        return style

    def _role(self, style_id: str | None) -> Role:
        style = self._paragraph_style(style_id)
        if style is None:
            return TEXT
        label = style.get(_STYLE_ID) or ""
        if not label:
            return TEXT
        name = _name(style)
        base = self._by_id.get(_val(style.find(_BASED_ON)) or "")
        if base is not None and base.get(_TYPE) not in ("paragraph", "table"):
            base = None
        base_label = base.get(_STYLE_ID) if base is not None else None
        base_name = _name(base) if base is not None else None

        if ":" in label and len(label.split(":")) == 2:
            head, level = label.split(":")
            return _role_of(head, _int(level))
        candidates = [label, name, base_label, base_name]
        outline = _int(_val(style.find(f".//{OUTLINE_LVL}")))
        outline = outline + 1 if outline is not None and 0 <= outline <= 8 else None
        named = next((c for c in candidates if c and "heading" in c.lower()), None)
        if named is not None:
            if outline is not None:
                return Role("heading", outline)
            return _role_of(*_heading_and_level(named))
        if outline is not None and not any(
            c and "title" in c.lower() for c in candidates
        ):
            return Role("heading", outline)
        return _role_of(label, None)

    def _numbering(self, style_id: str | None) -> StyleNumbering:
        """The list and level along w:basedOn, each from the nearest style
        that sets it: a level-2 style often names only its w:ilvl."""
        style = self._paragraph_style(style_id)
        num_id: str | None = None
        ilvl: int | None = None
        seen: set[str] = set()
        for _ in range(_CHAIN_LIMIT):
            if style is None or style.get(_STYLE_ID) in seen:
                break
            seen.add(style.get(_STYLE_ID))
            num_pr = style.find(f"{P_PR}/{NUM_PR}")
            if num_pr is not None:
                num_id = num_id or _val(num_pr.find(NUM_ID))
                ilvl = _int(_val(num_pr.find(ILVL))) if ilvl is None else ilvl
            if num_id is not None and ilvl is not None:
                break
            style = self._by_id.get(_val(style.find(_BASED_ON)) or "")
        return StyleNumbering(num_id, ilvl)


def _role_of(p_style_id: str, level: int | None) -> Role:
    # Docling's own tests of the label it settled on: case matters here.
    if p_style_id == "Title":
        return Role("title", 0)
    if "Heading" in p_style_id:
        return Role("heading", max(1, level or 1))
    return TEXT


def _heading_and_level(label: str) -> tuple[str, int | None]:
    match = _NAME_AND_NUMBER.match(label)
    if match is None:
        return label, None
    parts = sorted(part for part in match.groups() if part)
    if parts[0].strip().lower() == "heading":
        return "Heading", max(1, _int(parts[1]) or 0)
    if parts[1].strip().lower() == "heading":
        return "Heading", max(1, _int(parts[0]) or 0)
    return "", 1


def _name(style: Any) -> str:
    return _val(style.find(_NAME)) or ""


def _val(element: Any | None) -> str | None:
    return None if element is None else element.get(VAL)


def _int(text: str | None) -> int | None:
    try:
        return int(text) if text is not None else None
    except ValueError:
        return None
