import re
from urllib.parse import SplitResult, parse_qs

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
from modules.documents.web_sources.source_text.subtitles import transcript

_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com"}
# The video paths the plugin's resolver reads as one video; `watch?v=` aside.
_VIDEO_PATH = re.compile(r"^/(shorts|embed|v)/[\w-]+/?$")


def _fit(url: SplitResult) -> Fit | None:
    if url.hostname == "youtu.be":
        return Fit.ONE if url.path.strip("/") else None
    if url.hostname not in _HOSTS:
        return None
    if url.path == "/watch" and parse_qs(url.query).get("v"):
        return Fit.ONE
    return Fit.ONE if _VIDEO_PATH.match(url.path) else Fit.LIST


def _calls(url: str) -> list[ToolCall]:
    """The video with its subtitles, and its comments most-liked first."""
    return [
        ToolCall(
            "scrape", {"urls": [url], "max_results": 1, "download_subtitles": True}
        ),
        ToolCall(
            "comments",
            {"urls": [url], "max_comments": MAX_REPLIES, "sort_by": "TOP_COMMENTS"},
            optional=True,
        ),
    ]


def _written(url: str, results: Results) -> Pulled | None:
    video = next(iter(results.get("scrape") or []), None)
    if video is None:
        return None
    title = video.get("title") or url
    markdown = source_markdown(
        title,
        [
            ("Channel", video.get("channelName")),
            ("Published", video.get("date")),
            ("Duration", video.get("duration")),
            ("Views", video.get("viewCount")),
            ("Likes", video.get("likes")),
            ("Link", video.get("url") or url),
        ],
        [
            ("Description", video.get("text")),
            ("Transcript", _transcript(video.get("subtitles") or [])),
            ("Comments", bullets(_comment(c) for c in results.get("comments") or [])),
        ],
    )
    return Pulled(title, markdown)


def _transcript(tracks: list[dict]) -> str | None:
    """A track a person wrote before one YouTube generated."""
    with_text = [track for track in tracks if track.get("srt")]
    if not with_text:
        return None
    chosen = next(
        (t for t in with_text if t.get("type") == "user_generated"), with_text[0]
    )
    return transcript(chosen["srt"])


def _comment(comment: dict) -> str:
    text = (comment.get("comment") or "").strip()
    if not text:
        return ""
    replying = ", replying" if comment.get("replyToCid") else ""
    likes = count(comment.get("voteCount"), "likes")
    return f"**{comment.get('author') or 'Someone'}**{replying}{likes}: {text}"


def _list_call(url: str, count: int) -> ToolCall:
    """A channel caps its videos, shorts and streams apart: more may come back."""
    return ToolCall("scrape", {"urls": [url], "max_results": count})


def _list_items(items: list[dict]) -> list[Listed]:
    return [
        Listed(
            video["url"],
            video.get("title") or video["url"],
            about(video.get("channelName"), video.get("duration")),
        )
        for video in items
        if video.get("url")
    ]


def _search_call(query: str, count: int) -> ToolCall:
    return ToolCall("scrape", {"search_queries": [query], "max_results": count})


PULLER = Puller(
    id="youtube",
    plugin_id="youtube",
    fit=_fit,
    calls=_calls,
    written=_written,
    listing=Listing(_list_call, _list_items),
    search=_search_call,
)
