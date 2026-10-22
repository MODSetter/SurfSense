"""A post page's ``<shreddit-comment>`` elements as the nested ``t1`` tree ``.json`` gave."""

from __future__ import annotations

from typing import Any

from lxml import html

from .document import epoch, number, rich_text


def comment_tree(
    pages: list[html.HtmlElement], post: dict[str, Any]
) -> list[dict[str, Any]]:
    """Top-level ``t1`` children of every batch, each holding its replies as a Listing."""
    roots: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    elements = [
        element for page in pages for element in page.xpath("//shreddit-comment")
    ]
    for element in elements:
        data = _comment_data(element, post)
        thing = {"kind": "t1", "data": data}
        by_id[data["name"]] = thing
        parent = by_id.get(data["parent_id"])
        if parent is None:
            roots.append(thing)
        else:
            parent["data"]["replies"]["data"]["children"].append(thing)
    return roots


def count(tree: list[dict[str, Any]]) -> int:
    return sum(1 + count(t["data"]["replies"]["data"]["children"]) for t in tree)


def _comment_data(element: html.HtmlElement, post: dict[str, Any]) -> dict[str, Any]:
    attrs = element.attrib
    fullname = attrs.get("thingid") or ""
    bodies = element.xpath(f'.//*[@id="{fullname}-comment-rtjson-content"]')
    return {
        "name": fullname,
        "id": fullname.split("_", 1)[1] if "_" in fullname else None,
        "permalink": attrs.get("permalink"),
        "author": attrs.get("author"),
        "body": rich_text(bodies[0]) if bodies else None,
        "score": number(attrs.get("score")),
        "subreddit": post.get("subreddit"),
        "subreddit_name_prefixed": post.get("subreddit_name_prefixed"),
        "over_18": post.get("over_18"),
        "link_id": attrs.get("postid") or post.get("name"),
        "parent_id": attrs.get("parentid") or attrs.get("postid") or post.get("name"),
        "created_utc": epoch(attrs.get("created")),
        "replies": {"kind": "Listing", "data": {"children": []}},
    }
