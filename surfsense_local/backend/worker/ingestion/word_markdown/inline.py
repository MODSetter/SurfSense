"""A paragraph's words as Word shows them: runs, links, fields, tabs and breaks."""

import re
from collections.abc import Callable, Iterator
from typing import Any
from urllib.parse import quote

from worker.ingestion.word_markdown.alternate_content import shown_alternative
from worker.ingestion.word_markdown.ooxml_names import (
    A_T,
    CUSTOM_XML,
    HYPERLINK,
    M_OMATH,
    M_OMATH_PARA,
    M_T,
    MC_ALTERNATE_CONTENT,
    MC_FALLBACK,
    R_ID,
    SDT,
    SDT_CONTENT,
    TXBX_CONTENT,
    R,
    T,
    w,
)

# Wrappers whose runs are shown: tracked insertions, moves in, fields, tags.
_SHOWN_WRAPPERS = frozenset(
    {
        w("ins"),
        w("moveTo"),
        w("smartTag"),
        w("fldSimple"),
        w("dir"),
        w("bdo"),
        CUSTOM_XML,
    }
)
_TAB = frozenset({w("tab"), w("ptab")})
_BR = w("br")
_TYPE = w("type")
_CR = w("cr")
_NO_BREAK_HYPHEN = w("noBreakHyphen")
_FOOTNOTE_REFERENCE = w("footnoteReference")
_ENDNOTE_REFERENCE = w("endnoteReference")
_ID = w("id")
_RUBY = w("ruby")
_RUBY_BASE = w("rubyBase")
_SPACES = re.compile(r"[ \t]+")
_WHITESPACE = re.compile(r"\s")

LinkTarget = Callable[[str], str | None]
NoteMark = Callable[[str, str], str]


def inline_text(paragraph: Any, link_target: LinkTarget, note_mark: NoteMark) -> str:
    """The paragraph's text, one line per line break, a link as [text](address)."""
    pieces: list[str] = []
    _content(paragraph, pieces, link_target, note_mark)
    return tidy("".join(pieces))


def tidy(text: str) -> str:
    lines = (_SPACES.sub(" ", line).strip() for line in text.split("\n"))
    return "\n".join(line for line in lines if line)


def textboxes_in(paragraph: Any) -> list[Any]:
    """Each text box drawn in the paragraph once: Word stores a VML copy as the
    fallback of the modern one."""
    return [
        box
        for box in paragraph.iter(TXBX_CONTENT)
        if not _inside(box, paragraph, (MC_FALLBACK, TXBX_CONTENT))
    ]


def shape_text(paragraph: Any) -> str:
    """The words of a drawn shape that holds no text box, as Docling reads them."""
    words = [
        t.text
        for t in paragraph.iter(A_T)
        if t.text and not _inside(t, paragraph, (MC_FALLBACK,))
    ]
    return tidy(" ".join(words))


def _content(
    container: Any, pieces: list[str], link_target: LinkTarget, note_mark: NoteMark
) -> None:
    for child in container.iterchildren():
        tag = child.tag
        if tag == R:
            pieces.extend(_run(child, note_mark))
        elif tag == HYPERLINK:
            pieces.append(_link(child, link_target, note_mark))
        elif tag in _SHOWN_WRAPPERS:
            _content(child, pieces, link_target, note_mark)
        elif tag == SDT:
            shown = child.find(SDT_CONTENT)
            if shown is not None:
                _content(shown, pieces, link_target, note_mark)
        elif tag == MC_ALTERNATE_CONTENT:
            shown = shown_alternative(child)
            if shown is not None:
                _content(shown, pieces, link_target, note_mark)
        elif tag in (M_OMATH, M_OMATH_PARA):
            pieces.append("".join(t.text or "" for t in child.iter(M_T)))
        # Deleted text, moves out, bookmarks and comment marks show nothing.


def _run(run: Any, note_mark: NoteMark) -> Iterator[str]:
    for child in run.iterchildren():
        tag = child.tag
        if tag == T:
            yield child.text or ""
        elif tag in _TAB:
            yield " "
        elif tag == _BR:
            # A page or column break still parts the words either side.
            yield "\n" if child.get(_TYPE) in (None, "textWrapping") else " "
        elif tag == _CR:
            yield "\n"
        elif tag == _NO_BREAK_HYPHEN:
            yield "-"
        elif tag == _FOOTNOTE_REFERENCE:
            yield note_mark("footnote", child.get(_ID, ""))
        elif tag == _ENDNOTE_REFERENCE:
            yield note_mark("endnote", child.get(_ID, ""))
        elif tag == _RUBY:
            # The text a reading guide sits over; the guide itself is a reading aid.
            base = child.find(_RUBY_BASE)
            if base is not None:
                yield from _base_runs(base, note_mark)


def _base_runs(base: Any, note_mark: NoteMark) -> Iterator[str]:
    for child in base.iterchildren():
        if child.tag == R:
            yield from _run(child, note_mark)
        elif child.tag in _SHOWN_WRAPPERS:
            yield from _base_runs(child, note_mark)


def _link(hyperlink: Any, link_target: LinkTarget, note_mark: NoteMark) -> str:
    pieces: list[str] = []
    _content(hyperlink, pieces, link_target, note_mark)
    raw = "".join(pieces)
    text = tidy(raw).replace("\n", " ")
    r_id = hyperlink.get(R_ID)
    address = link_target(r_id) if r_id else None
    shown = f"[{text}]({_destination(address)})" if text and address else text
    # Spaces at the link's edges still part it from the words around it.
    before = " " if raw[:1].isspace() else ""
    after = " " if raw[-1:].isspace() else ""
    return f"{before}{shown}{after}"


def _destination(address: str) -> str:
    """The address as a markdown link destination, which ends at a space or at
    an unmatched parenthesis: spaces as %20, as Docling writes them."""
    address = _WHITESPACE.sub(lambda space: quote(space.group()), address)
    depth = 0
    for character in address:
        depth += {"(": 1, ")": -1}.get(character, 0)
        if depth < 0:
            break
    if depth != 0:
        address = address.replace("(", "%28").replace(")", "%29")
    return address


def _inside(element: Any, top: Any, tags: tuple[str, ...]) -> bool:
    for ancestor in element.iterancestors():
        if ancestor is top:
            return False
        if ancestor.tag in tags:
            return True
    return False
