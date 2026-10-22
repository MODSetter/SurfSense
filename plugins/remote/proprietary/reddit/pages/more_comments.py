"""The request a comment page's top-level "more comments" partial makes for the next batch."""

from __future__ import annotations

from typing import NamedTuple
from urllib.parse import parse_qsl, urlsplit

from lxml import html


class MoreComments(NamedTuple):
    route: str
    params: dict[str, str]
    form: dict[str, str]


def more_comments(page: html.HtmlElement) -> MoreComments | None:
    """The POST that loads the next top-level comments, or ``None`` when none remain.

    Nested "more replies" partials are not followed: the old ``.json`` read
    stopped at its ``more`` stubs too.
    """
    for partial in page.xpath('//faceplate-partial[contains(@src, "top-level=1")]'):
        parts = urlsplit(partial.get("src", ""))
        if "/more-comments/" not in parts.path:
            continue
        cursors = partial.xpath('.//input[@name="cursor"]/@value')
        if cursors:
            return MoreComments(
                parts.path.lstrip("/"),
                dict(parse_qsl(parts.query)),
                {"cursor": cursors[0]},
            )
    return None
