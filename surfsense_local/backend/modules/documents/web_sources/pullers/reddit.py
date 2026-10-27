from urllib.parse import SplitResult, urlsplit, urlunsplit

from modules.documents.web_sources.pullers.puller import (
    Fit,
    Listed,
    Listing,
    Pulled,
    Puller,
    Results,
    ToolCall,
)
from modules.documents.web_sources.source_text.source_markdown import (
    about,
    bullets,
    count,
    source_markdown,
)

# The most items one `scrape` returns, the post included.
_MAX_ITEMS = 100

_HOSTS = {
    "reddit.com",
    "www.reddit.com",
    "old.reddit.com",
    "new.reddit.com",
    "np.reddit.com",
    "m.reddit.com",
}
# Redirects only: the plugin follows none of them.
_SHORT_HOSTS = {"redd.it"}


def _fit(url: SplitResult) -> Fit | None:
    if url.hostname in _SHORT_HOSTS:
        return Fit.SHORT_LINK
    if url.hostname not in _HOSTS:
        return None
    segments = [s for s in url.path.split("/") if s]
    if segments and segments[-1] == "search":
        return Fit.LIST if "q=" in url.query else None
    if len(segments) >= 2 and segments[0] == "r":
        if len(segments) >= 4 and segments[2] == "comments":
            return Fit.ONE
        # A share link, `/r/<sub>/s/<code>`, which the plugin would read as the subreddit.
        if len(segments) >= 3 and segments[2] == "s":
            return Fit.SHORT_LINK
        return Fit.LIST
    if len(segments) >= 2 and segments[0] in ("user", "u"):
        return Fit.LIST
    return None


def _calls(url: str) -> list[ToolCall]:
    return [
        ToolCall(
            "scrape",
            {"urls": [url], "max_comments": _MAX_ITEMS - 1, "max_items": _MAX_ITEMS},
        )
    ]


def _written(url: str, results: Results) -> Pulled | None:
    items = results.get("scrape") or []
    post = next((item for item in items if item.get("dataType") == "post"), None)
    if post is None:
        return None
    title = (
        post.get("title") or f"Reddit post in {post.get('communityName') or 'Reddit'}"
    )
    comments = [item for item in items if item.get("dataType") == "comment"]
    markdown = source_markdown(
        title,
        [
            ("Subreddit", post.get("communityName")),
            ("Author", _user(post.get("username"))),
            ("Posted", post.get("createdAt")),
            ("Score", post.get("upVotes")),
            ("Comments", post.get("numberOfComments")),
            ("Flair", post.get("flair")),
            ("Shares", post.get("link")),
            ("Link", post.get("url")),
        ],
        [
            ("Post", post.get("body")),
            ("Comments", bullets(_comment(c) for c in comments)),
        ],
    )
    return Pulled(title, markdown)


def _user(name: str | None) -> str | None:
    return f"u/{name}" if name else None


def _comment(comment: dict) -> str:
    text = (comment.get("body") or "").strip()
    if not text:
        return ""
    who = _user(comment.get("username")) or "Someone"
    # A top-level comment's parent is the post, `t3_`; a reply's is a comment, `t1_`.
    replying = ", replying" if (comment.get("parentId") or "").startswith("t1_") else ""
    return f"**{who}**{replying}{count(comment.get('upVotes'), 'points')}: {text}"


def _list_call(url: str, count: int) -> ToolCall:
    # The subreddit's own item comes first, one more item than its posts.
    return ToolCall(
        "scrape",
        {
            "urls": [_submitted(url)],
            "skip_comments": True,
            "max_posts": count,
            "max_items": min(count + 1, _MAX_ITEMS),
        },
    )


def _submitted(url: str) -> str:
    """A user's posts, not their overview or comments, which mix in comments."""
    parts = urlsplit(url)
    segments = [s for s in parts.path.split("/") if s]
    if len(segments) >= 2 and segments[0] in ("user", "u"):
        path = f"/user/{segments[1]}/submitted"
        return urlunsplit((parts.scheme, parts.netloc, path, "", ""))
    return url


def _list_items(items: list[dict]) -> list[Listed]:
    return [
        Listed(
            post["url"],
            post.get("title") or post["url"],
            about(post.get("communityName"), _user(post.get("username"))),
        )
        for post in items
        if post.get("dataType") == "post" and post.get("url")
    ]


def _search_call(query: str, count: int) -> ToolCall:
    return ToolCall(
        "scrape",
        {
            "search_queries": [query],
            "skip_comments": True,
            "max_posts": count,
            "max_items": count,
        },
    )


PULLER = Puller(
    id="reddit",
    plugin_id="reddit",
    fit=_fit,
    calls=_calls,
    written=_written,
    listing=Listing(_list_call, _list_items),
    search=_search_call,
)
