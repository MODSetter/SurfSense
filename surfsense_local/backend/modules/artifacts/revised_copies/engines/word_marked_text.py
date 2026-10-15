"""A Word copy's body as text with every author's tracked changes marked inline, and its comments.

The agent quotes this text to edit again, so deleted text is marked rather than
dropped, and each comment names what it is on.
"""

from collections.abc import Collection
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

from modules.artifacts.revised_copies.engines.package import open_package
from modules.artifacts.revised_copies.engines.word import main_part
from modules.artifacts.revised_copies.engines.word_xml import (
    COMMENT_END,
    COMMENT_REF,
    COMMENT_START,
    COMMENTS_REL,
    DEL,
    DEL_TEXT,
    INS,
    MOVE_FROM,
    MOVE_TO,
    NOT_TEXT,
    P,
    T,
    w,
)

_SKIPPED = NOT_TEXT - {DEL, MOVE_FROM}
_MARKS = {INS: "ins", MOVE_TO: "ins", DEL: "del", MOVE_FROM: "del"}
_SPACES = frozenset({w("tab"), w("ptab"), w("br"), w("cr")})
_ANCHOR_CHARS = 200


@dataclass(frozen=True)
class CommentNote:
    id: str
    author: str
    anchor: str  # the text it is on, as it reads now
    text: str
    internal: bool


@dataclass(frozen=True)
class MarkedText:
    paragraphs: tuple[str, ...]
    comments: tuple[CommentNote, ...]


@dataclass
class _Paragraph:
    # (mark, text): mark is None, ("ins"|"del", author), or "comment" for a marker.
    pieces: list[tuple[object, str]] = field(default_factory=list)

    def add(self, mark: object, text: str) -> None:
        if self.pieces and self.pieces[-1][0] == mark and mark != "comment":
            self.pieces[-1] = (mark, self.pieces[-1][1] + text)
        else:
            self.pieces.append((mark, text))

    def render(self) -> str:
        out = []
        for mark, text in self.pieces:
            if mark is None:
                out.append(text)
            elif mark == "comment":
                out.append(f"[comment {text}]")
            else:
                kind, author = mark
                out.append(f'<{kind} author="{author}">{text}</{kind}>')
        return "".join(out).strip()


def marked_text(path: Path, internal_ids: Collection[str]) -> MarkedText:
    """Every body paragraph in reading order, then every comment with what it is on."""
    package = open_package(path)
    main = main_part(package)
    body = package.xml(main).find(w("body"))
    anchors: dict[str, list[str]] = {}
    open_ranges: set[str] = set()
    marked: set[str] = set()
    found: list[_Paragraph] = []

    def walk(element: etree._Element, current: _Paragraph | None, mark: object) -> None:
        for child in element:
            tag = child.tag
            if not isinstance(tag, str) or tag in _SKIPPED:
                continue
            if tag == P:
                paragraph = _Paragraph()
                found.append(paragraph)
                walk(child, paragraph, mark)
            elif tag in _MARKS:
                walk(child, current, (_MARKS[tag], child.get(w("author")) or "unknown"))
            elif tag == COMMENT_START:
                comment_id = child.get(w("id"), "")
                anchors.setdefault(comment_id, [])
                open_ranges.add(comment_id)
            elif tag in (COMMENT_END, COMMENT_REF):
                comment_id = child.get(w("id"), "")
                open_ranges.discard(comment_id)
                if current is not None and comment_id not in marked:
                    marked.add(comment_id)
                    current.add("comment", comment_id)
            elif current is not None and tag in (T, DEL_TEXT):
                write(current, mark, child.text or "")
            elif current is not None and tag in _SPACES:
                write(current, mark, " ")
            elif current is not None and tag == w("noBreakHyphen"):
                write(current, mark, "-")
            else:
                walk(child, current, mark)

    def write(paragraph: _Paragraph, mark: object, text: str) -> None:
        paragraph.add(mark, text)
        if not (isinstance(mark, tuple) and mark[0] == "del"):
            for comment_id in open_ranges:
                anchors[comment_id].append(text)

    walk(body, None, None)
    paragraphs = tuple(text for text in (p.render() for p in found) if text)
    internal = {str(i) for i in internal_ids}
    comments = tuple(
        CommentNote(
            comment_id,
            author,
            _shortened(" ".join("".join(anchors.get(comment_id, [])).split())),
            text,
            comment_id in internal,
        )
        for comment_id, author, text in _comments(package, main)
    )
    return MarkedText(paragraphs, comments)


def _comments(package, main: str) -> list[tuple[str, str, str]]:
    found = []
    for name in package.related(main, COMMENTS_REL):
        if name not in package.names:
            continue
        for comment in package.xml(name).iter(w("comment")):
            lines = (
                "".join(t.text or "" for t in paragraph.iter(T))
                for paragraph in comment.iter(P)
            )
            text = " ".join(line for line in lines if line)
            found.append(
                (comment.get(w("id"), ""), comment.get(w("author")) or "unknown", text)
            )
    return found


def _shortened(anchor: str) -> str:
    if len(anchor) <= _ANCHOR_CHARS:
        return anchor
    return anchor[: _ANCHOR_CHARS - 3] + "..."
