"""SurfSense's YouTube plugin: public videos, channels, playlists and comments, behind the license."""

import json
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, ToolAnnotations
from pydantic import Field

from mcp_server.progress import stage
from mcp_server.results import (
    CLIP_CHARS,
    ELLIPSIS,
    MAX_TEXT_BYTES,
    tool_result,
    wants_text_only,
)
from proprietary.license_check.license_access import shared_access
from proprietary.scraping import lifecycle
from proprietary.youtube.comments import scrape_comments
from proprietary.youtube.innertube import on_stage
from proprietary.youtube.schemas import YouTubeCommentsInput, YouTubeScrapeInput
from proprietary.youtube.scraper import scrape_youtube

# Bound one call's fan-out and its result, as the scraper API's did.
MAX_SOURCES = 20
MAX_RESULTS = 1000
MAX_COMMENT_VIDEOS = 20
MAX_COMMENTS = 100_000

# The text's bytes besides the items: the summary and the "more items" line.
_TEXT_HEAD_BYTES = 500

access = shared_access()


@asynccontextmanager
async def lifespan() -> AsyncIterator[None]:
    """Closes the kept proxy sessions at shutdown; nothing to warm (all HTTP)."""
    async with lifecycle.lifespan():
        yield


CommentOrder = Literal["TOP_COMMENTS", "NEWEST_FIRST"]


def server() -> MCPServer:
    youtube = MCPServer("youtube")

    @youtube.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def scrape(
        ctx: Context,
        urls: Annotated[
            list[str],
            Field(
                max_length=MAX_SOURCES,
                description=(
                    "YouTube URLs to scrape: video, channel (/@handle or "
                    "/channel/UC...), playlist (?list=...), shorts, or hashtag pages. "
                    "Give these or search_queries."
                ),
            ),
        ] = [],  # noqa: B006 - read only, and the schema shows the default
        search_queries: Annotated[
            list[str],
            Field(
                max_length=MAX_SOURCES,
                description=(
                    "Search terms to run on YouTube; each returns up to max_results "
                    "videos. Give these or urls."
                ),
            ),
        ] = [],  # noqa: B006
        max_results: Annotated[
            int,
            Field(
                ge=1,
                le=MAX_RESULTS,
                description=(
                    "Most items per source and per content type: a channel's "
                    "videos, shorts and streams are capped independently."
                ),
            ),
        ] = 10,
        download_subtitles: Annotated[
            bool,
            Field(description="Also fetch each video's subtitle track: slower."),
        ] = False,
        subtitles_language: Annotated[
            str,
            Field(
                description=(
                    "Subtitle language code, such as 'en' or 'fr'. Used when "
                    "download_subtitles is true; a language other than 'en' also "
                    "fills translatedTitle and translatedText."
                )
            ),
        ] = "en",
    ) -> CallToolResult:
        """Scrape public YouTube videos, channels, playlists, and subtitles.

        A video's commentsCount is approximate: YouTube rounds it (3.3K).
        """
        if not urls and not search_queries:
            raise ToolError("Give at least one of urls or search_queries.")
        urls = _http_urls(urls)
        sources = len(urls) + len(search_queries)
        await stage(ctx, f"scraping {sources} YouTube sources")

        async def heard(count: int) -> None:
            await stage(ctx, f"{count} items", done=count)

        # A channel emits three content types; each takes the caller's cap.
        request = YouTubeScrapeInput(
            startUrls=[{"url": url} for url in urls],
            searchQueries=search_queries,
            maxResults=max_results,
            maxResultsShorts=max_results,
            maxResultStreams=max_results,
            downloadSubtitles=download_subtitles,
            subtitlesLanguage=subtitles_language,
        )
        with _stages(ctx):
            items = await scrape_youtube(request, on_item=heard)
        return tool_result(
            f"{len(items)} YouTube items",
            items,
            # A transcript is the point of asking for one: each video's is cut
            # to its share of the byte cap, not to CLIP_CHARS.
            project=_video_sharing_cap(len(items)) if download_subtitles else _video,
            clip_chars=MAX_TEXT_BYTES if download_subtitles else CLIP_CHARS,
            text_only=wants_text_only(ctx),
        )

    @youtube.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def comments(
        ctx: Context,
        urls: Annotated[
            list[str],
            Field(
                min_length=1,
                max_length=MAX_COMMENT_VIDEOS,
                description="YouTube video URLs to fetch comments and replies for.",
            ),
        ],
        max_comments: Annotated[
            int,
            Field(
                ge=1,
                le=MAX_COMMENTS,
                description="Most items per video, counting comments and replies.",
            ),
        ] = 20,
        sort_by: Annotated[
            CommentOrder,
            Field(description="Most-liked first, or most-recent first."),
        ] = "NEWEST_FIRST",
    ) -> CallToolResult:
        """Fetch public YouTube comments and replies with authors, text, likes, and timestamps.

        voteCount is approximate above 1K: YouTube rounds it (4.8M).
        """
        urls = _http_urls(urls)
        most = len(urls) * max_comments
        await stage(ctx, f"fetching comments for {len(urls)} videos", total=most)

        async def heard(count: int) -> None:
            await stage(ctx, f"{count} of {most} comments", done=count, total=most)

        request = YouTubeCommentsInput(
            startUrls=[{"url": url} for url in urls],
            maxComments=max_comments,
            sortCommentsBy=sort_by,
        )
        with _stages(ctx):
            items = await scrape_comments(request, on_item=heard)
        return tool_result(
            f"{len(items)} YouTube comments",
            items,
            project=_comment,
            text_only=wants_text_only(ctx),
        )

    return youtube


def _http_urls(urls: list[str]) -> list[str]:
    trimmed = [url.strip() for url in urls]
    for url in trimmed:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ToolError(f"Not an http(s) URL: {url}")
    return trimmed


@contextmanager
def _stages(ctx: Context) -> Iterator[None]:
    """Report each request of the call as a progress stage (rate-limited by stage())."""

    async def heard(message: str) -> None:
        await stage(ctx, message)

    token = on_stage.set(heard)
    try:
        yield
    finally:
        on_stage.reset(token)


def _video(item: dict[str, Any]) -> dict[str, Any]:
    """What an agent needs to answer about a video without another call."""
    return {
        "type": item.get("type"),
        "id": item.get("id"),
        "title": item.get("title"),
        "url": item.get("url"),
        "date": item.get("date"),
        # List pages give only this ("3 days ago"); date stays empty there.
        "publishedTimeText": item.get("publishedTimeText"),
        "duration": item.get("duration"),
        "viewCount": item.get("viewCount"),
        "likes": item.get("likes"),
        "commentsCount": item.get("commentsCount"),
        "channelName": item.get("channelName"),
        "channelUrl": item.get("channelUrl"),
        "numberOfSubscribers": item.get("numberOfSubscribers"),
        "hashtags": item.get("hashtags"),
        "translatedTitle": item.get("translatedTitle"),
        "text": item.get("text"),
        "translatedText": item.get("translatedText"),
        "subtitles": [
            {"language": track.get("language"), "srt": track.get("srt")}
            for track in item.get("subtitles") or []
        ],
    }


def _video_sharing_cap(count: int) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """``_video`` with each transcript cut to its video's share of the text cap.

    Every one of ``count`` videos gets an equal share, so all of them show, and a
    single video keeps nearly the whole cap. Other strings are cut at CLIP_CHARS,
    as without transcripts.
    """
    share = (MAX_TEXT_BYTES - _TEXT_HEAD_BYTES) // max(1, count)

    def project(item: dict[str, Any]) -> dict[str, Any]:
        video = {key: _clip(value) for key, value in _video(item).items()}
        tracks, video["subtitles"] = video["subtitles"], []
        room = (share - _json_size(video)) // max(1, len(tracks))
        for track in tracks:
            # The track's own keys and quotes, beyond its srt string.
            srt = _fit(track["srt"] or "", room - _json_size({**track, "srt": ""}))
            video["subtitles"].append({**track, "srt": srt})
        return video

    return project


def _clip(value: Any) -> Any:
    if isinstance(value, str) and len(value) > CLIP_CHARS:
        return value[:CLIP_CHARS] + ELLIPSIS
    return value


def _json_size(value: Any) -> int:
    """``value``'s bytes in the result text (as ``tool_result`` writes a line)."""
    line = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    return len(line.encode())


def _fit(text: str, room: int) -> str:
    """``text`` cut so it takes at most ``room`` bytes as a JSON string."""
    size = _json_size(text)
    if size <= room:
        return text
    if room <= _json_size(ELLIPSIS):
        return ""
    # Cut in proportion, then by the bytes still over: a character is at least
    # one byte, so dropping that many more fits.
    cut = text[: len(text) * room // size]
    over = _json_size(cut + ELLIPSIS) - room
    if over > 0:
        cut = cut[: max(0, len(cut) - over)]
    return cut + ELLIPSIS


def _comment(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "videoId": item.get("videoId"),
        "cid": item.get("cid"),
        "replyToCid": item.get("replyToCid"),
        "author": item.get("author"),
        "comment": item.get("comment"),
        "voteCount": item.get("voteCount"),
        "replyCount": item.get("replyCount"),
        "publishedTimeText": item.get("publishedTimeText"),
        "authorIsChannelOwner": item.get("authorIsChannelOwner"),
        "hasCreatorHeart": item.get("hasCreatorHeart"),
    }
