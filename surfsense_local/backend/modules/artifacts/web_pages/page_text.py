"""A page's searchable body (ADR 0003): its readable text as Markdown, without its code."""

import re
from html.parser import HTMLParser

# Never read by a person: code, styles, inert templates and the tab's title.
_HIDDEN = frozenset({"script", "style", "template", "noscript", "head"})
# Each opens a block of its own in the body.
_BLOCKS = frozenset(
    {
        "p", "div", "section", "article", "main", "header", "footer", "aside",
        "nav", "figure", "figcaption", "blockquote", "pre", "ul", "ol", "dl",
        "dt", "dd", "table", "caption", "form", "fieldset", "legend", "details",
        "summary", "svg", "title", "br", "hr",
    }
)  # fmt: skip
# Words of their own inside a block: an SVG chart's labels.
_WORDS = frozenset({"text", "tspan"})
_HEADINGS = {f"h{level}": level for level in range(1, 7)}
_SPACE = re.compile(r"\s+")


class _Reader(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self._line: list[str] = []
        self._prefix = ""
        self._hidden = 0
        self._cells: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _HIDDEN:
            self._hidden += 1
            return
        if self._hidden:
            return
        if tag in _HEADINGS:
            self._end_block()
            self._prefix = "#" * _HEADINGS[tag] + " "
        elif tag == "li":
            self._end_block()
            self._prefix = "- "
        elif tag == "tr":
            self._end_block()
            self._cells = []
        elif tag in ("td", "th") and self._cells is not None:
            self._end_cell()
        elif tag in _BLOCKS:
            self._end_block()
        if tag == "img":
            alt = dict(attrs).get("alt")
            if alt and alt.strip():
                self._end_block()
                self.blocks.append(_SPACE.sub(" ", alt).strip())

    def handle_endtag(self, tag: str) -> None:
        if tag in _HIDDEN:
            self._hidden = max(0, self._hidden - 1)
            return
        if self._hidden:
            return
        if tag in _WORDS:
            self._line.append(" ")
        elif tag == "tr":
            self._end_cell()
            cells, self._cells = self._cells or [], None
            if cells:
                self.blocks.append(" | ".join(cells))
        elif tag in ("td", "th"):
            self._end_cell()
        elif tag in _HEADINGS or tag == "li" or tag in _BLOCKS:
            self._end_block()

    def handle_data(self, data: str) -> None:
        if not self._hidden:
            self._line.append(data)

    def close(self) -> None:
        super().close()
        self._end_block()

    def _end_cell(self) -> None:
        text = self._take()
        if text and self._cells is not None:
            self._cells.append(text)

    def _end_block(self) -> None:
        if self._cells is not None:
            self._end_cell()
            return
        text = self._take()
        if text:
            self.blocks.append(self._prefix + text)
        self._prefix = ""

    def _take(self) -> str:
        text = _SPACE.sub(" ", "".join(self._line).replace("\xa0", " ")).strip()
        self._line = []
        return text


def page_text(page: str) -> str:
    """Headings, paragraphs, list items, table rows, alt text and SVG labels, one block each."""
    reader = _Reader()
    reader.feed(page)
    reader.close()
    return "\n\n".join(reader.blocks)
