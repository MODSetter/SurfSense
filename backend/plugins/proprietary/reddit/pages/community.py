"""A subreddit's ``<shreddit-subreddit-header>`` as the ``t5`` data ``about.json`` gave."""

from __future__ import annotations

from typing import Any

from lxml import html

from .document import number


def community_data(header: html.HtmlElement, *, over_18: bool) -> dict[str, Any]:
    """``over_18`` comes from the listing: the header does not say."""
    attrs = header.attrib
    fullname = attrs.get("subreddit-id") or ""
    name = attrs.get("name")
    return {
        "name": fullname or None,
        "id": fullname.split("_", 1)[1] if "_" in fullname else None,
        "url": f"/r/{name}/" if name else None,
        "title": attrs.get("display-name") or name,
        "public_description": attrs.get("description") or None,
        "display_name": name,
        "display_name_prefixed": attrs.get("prefixed-name"),
        "subscribers": number(attrs.get("subscribers")),
        "over18": over_18,
    }
