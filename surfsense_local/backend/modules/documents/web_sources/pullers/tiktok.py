import re
from urllib.parse import SplitResult, quote_plus

from modules.documents.web_sources.pullers.puller import (
    MAX_REPLIES,
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

# A caption's first line, as a title the sources list can show.
_TITLE_CHARACTERS = 120

_HOSTS = {"tiktok.com", "www.tiktok.com", "m.tiktok.com"}
# Redirects only: the plugin follows none of them.
_SHORT_HOSTS = {"vm.tiktok.com", "vt.tiktok.com"}
_VIDEO_PATH = re.compile(r"^/@[^/]+/video/\d+/?$")


def _fit(url: SplitResult) -> Fit | None:
    if url.hostname in _SHORT_HOSTS:
        return Fit.SHORT_LINK
    if url.hostname not in _HOSTS:
        return None
    return Fit.ONE if _VIDEO_PATH.match(url.path) else Fit.LIST


def _calls(url: str) -> list[ToolCall]:
    return [
        ToolCall("scrape", {"urls": [url], "max_items": 1}),
        ToolCall(
            "comments",
            {
                "video_urls": [url],
                "comments_per_video": MAX_REPLIES,
                "max_items": MAX_REPLIES,
            },
            optional=True,
        ),
    ]


def _written(url: str, results: Results) -> Pulled | None:
    # Errors, profiles and comments carry no `webVideoUrl`.
    video = next(
        (item for item in results.get("scrape") or [] if item.get("webVideoUrl")), None
    )
    if video is None:
        return None
    author = video.get("authorMeta") or {}
    handle = f"@{author['name']}" if author.get("name") else None
    caption = (video.get("text") or "").strip()
    title = caption.splitlines()[0][:_TITLE_CHARACTERS] if caption else None
    title = title or f"TikTok video by {handle or 'someone'}"
    duration = (video.get("videoMeta") or {}).get("duration")
    tags = [f"#{tag['name']}" for tag in video.get("hashtags") or [] if tag.get("name")]
    markdown = source_markdown(
        title,
        [
            ("Author", _author(author.get("nickName"), handle)),
            ("Posted", video.get("createTimeISO")),
            ("Duration", f"{duration} s" if duration else None),
            ("Plays", video.get("playCount")),
            ("Likes", video.get("diggCount")),
            ("Hashtags", tags),
            ("Link", video.get("webVideoUrl")),
        ],
        [
            ("Caption", caption),
            ("Comments", bullets(_comment(c) for c in results.get("comments") or [])),
        ],
    )
    return Pulled(title, markdown)


def _author(name: str | None, handle: str | None) -> str | None:
    if name and handle:
        return f"{name} ({handle})"
    return name or handle


def _comment(comment: dict) -> str:
    text = (comment.get("text") or "").strip()
    if not text:
        return ""
    who = f"@{comment['uniqueId']}" if comment.get("uniqueId") else "Someone"
    replying = ", replying" if comment.get("repliesToId") else ""
    return f"**{who}**{replying}{count(comment.get('diggCount'), 'likes')}: {text}"


def _list_call(url: str, count: int) -> ToolCall:
    return ToolCall(
        "scrape", {"urls": [url], "results_per_page": count, "max_items": count}
    )


def _list_items(items: list[dict]) -> list[Listed]:
    # A profile's own account comes first, with no `webVideoUrl`.
    listed = []
    for video in items:
        if not video.get("webVideoUrl"):
            continue
        name = (video.get("authorMeta") or {}).get("name")
        caption = (video.get("text") or "").strip()
        title = caption.splitlines()[0][:_TITLE_CHARACTERS] if caption else None
        listed.append(
            Listed(
                video["webVideoUrl"],
                title or video["webVideoUrl"],
                about(f"@{name}" if name else None),
            )
        )
    return listed


def _search_call(query: str, count: int) -> ToolCall:
    """TikTok's own search page, which the plugin reads like any list link."""
    url = f"https://www.tiktok.com/search?q={quote_plus(query)}"
    return _list_call(url, count)


PULLER = Puller(
    id="tiktok",
    plugin_id="tiktok",
    fit=_fit,
    calls=_calls,
    written=_written,
    listing=Listing(_list_call, _list_items),
    search=_search_call,
)
