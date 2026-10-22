"""A logged-out Reddit page parsed whole, for the readers that pick items out of it."""

from __future__ import annotations

from datetime import datetime

from lxml import html


def parse(text: str) -> html.HtmlElement:
    """The page's tree; Reddit streams the comment tree after ``</html>``, so keep it."""
    return html.document_fromstring(
        text.replace("</html>", "").replace("</body>", "") or "<html></html>"
    )


def rich_text(element: html.HtmlElement | None) -> str | None:
    """A body's paragraphs as plain text, one blank line between them."""
    if element is None:
        return None
    blocks = [child.text_content().strip() for child in element]
    text = "\n\n".join(block for block in blocks if block)
    return text or element.text_content().strip() or None


def epoch(timestamp: str | None) -> float | None:
    """``2026-10-22T09:56:06.051000+0000`` as epoch seconds, as ``.json`` gave it."""
    if not timestamp:
        return None
    try:
        return datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%f%z").timestamp()
    except ValueError:
        return None


def number(value: str | None) -> int | float | None:
    """An attribute's count or ratio; Reddit writes both as plain digits."""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return None
