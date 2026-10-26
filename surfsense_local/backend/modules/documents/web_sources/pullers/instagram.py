from urllib.parse import SplitResult, urlsplit

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
    source_markdown,
)

# A caption's first line, as a title the sources list can show.
_TITLE_CHARACTERS = 120

_HOSTS = {"instagram.com", "www.instagram.com", "m.instagram.com"}
# Redirects only: the plugin follows none of them.
_SHORT_HOSTS = {"instagr.am"}
_ONE = {"p", "reel", "reels"}
_SHORT = {"s", "share"}
# Pages that are not a profile; hashtags, places and stories are behind the login.
_NOT_PROFILES = {"tv", "explore", "stories", "accounts", "direct"}


def _fit(url: SplitResult) -> Fit | None:
    if url.hostname in _SHORT_HOSTS:
        return Fit.SHORT_LINK
    if url.hostname not in _HOSTS:
        return None
    segments = [s for s in url.path.split("/") if s]
    if not segments:
        return None
    head = segments[0]
    if head in _ONE:
        return Fit.ONE if len(segments) >= 2 else None
    if head in _SHORT:
        return Fit.SHORT_LINK
    return None if head in _NOT_PROFILES else Fit.LIST


def _calls(url: str) -> list[ToolCall]:
    return [ToolCall("scrape", {"urls": [url], "max_items": 1})]


def _written(url: str, results: Results) -> Pulled | None:
    post = next((item for item in results.get("scrape") or [] if _is_post(item)), None)
    if post is None:
        return None
    handle = f"@{post['ownerUsername']}" if post.get("ownerUsername") else None
    caption = (post.get("caption") or "").strip()
    title = _caption_title(caption) or f"Instagram post by {handle or 'someone'}"
    markdown = source_markdown(
        title,
        [
            ("Author", _author(post.get("ownerFullName"), handle)),
            ("Posted", post.get("timestamp")),
            ("Plays", post.get("videoPlayCount") or post.get("videoViewCount")),
            ("Likes", post.get("likesCount")),
            ("Comments", post.get("commentsCount")),
            ("Hashtags", [f"#{tag}" for tag in post.get("hashtags") or []]),
            ("Location", post.get("locationName")),
            ("Link", post.get("url")),
        ],
        [
            ("Caption", caption),
            ("Image description", post.get("alt")),
        ],
    )
    return Pulled(title, markdown)


def _is_post(item: dict) -> bool:
    """Error and profile items carry no post of their own."""
    return (
        bool(item.get("url")) and not item.get("error") and not item.get("detailKind")
    )


def _caption_title(caption: str) -> str | None:
    return caption.splitlines()[0][:_TITLE_CHARACTERS] if caption else None


def _author(name: str | None, handle: str | None) -> str | None:
    if name and handle:
        return f"{name} ({handle})"
    return name or handle


def _list_call(url: str, count: int) -> ToolCall:
    arguments: dict = {"urls": [url], "max_per_target": count, "max_items": count}
    # The plugin reads /<user>/reels/ as the profile, and its feed defaults to posts.
    segments = [s for s in urlsplit(url).path.split("/") if s]
    if segments[1:] == ["reels"]:
        arguments["result_type"] = "reels"
    return ToolCall("scrape", arguments)


def _list_items(items: list[dict]) -> list[Listed]:
    """A profile's posts, or the profiles a search found, each opened in turn."""
    listed = []
    for item in items:
        if item.get("detailKind") == "profile" and item.get("url"):
            handle = f"@{item['username']}" if item.get("username") else None
            followers = item.get("followersCount")
            listed.append(
                Listed(
                    item["url"],
                    item.get("fullName") or handle or item["url"],
                    about(
                        handle,
                        f"{followers:,} followers"
                        if isinstance(followers, int)
                        else None,
                    ),
                )
            )
        elif _is_post(item):
            owner = item.get("ownerUsername")
            listed.append(
                Listed(
                    item["url"],
                    _caption_title((item.get("caption") or "").strip()) or item["url"],
                    about(f"@{owner}" if owner else None),
                )
            )
    return listed


def _search_call(query: str, count: int) -> ToolCall:
    """Instagram's own search is behind the login: the plugin finds profiles by Google."""
    return ToolCall(
        "details",
        {"search_queries": [query], "search_limit": count, "max_items": count},
    )


PULLER = Puller(
    id="instagram",
    plugin_id="instagram",
    fit=_fit,
    calls=_calls,
    written=_written,
    listing=Listing(_list_call, _list_items),
    search=_search_call,
)
