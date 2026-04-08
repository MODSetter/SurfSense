"""YouTube utility routes (playlist resolution)."""

import json
import logging
import re

import aiohttp
from fake_useragent import UserAgent
from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import User
from app.users import current_active_user
from app.utils.proxy_config import get_requests_proxies

router = APIRouter()
logger = logging.getLogger(__name__)

_PLAYLIST_ID_RE = re.compile(r"[?&]list=([\w-]+)")

_INNERTUBE_API_URL = "https://www.youtube.com/youtubei/v1/browse"
_INNERTUBE_CLIENT = {
    "clientName": "WEB",
    "clientVersion": "2.20240313.05.00",
    "hl": "en",
    "gl": "US",
}


@router.get("/youtube/playlist-videos")
async def get_playlist_videos(
    url: str = Query(..., description="YouTube playlist URL"),
    _user: User = Depends(current_active_user),
):
    """Resolve a YouTube playlist URL into individual video URLs."""
    match = _PLAYLIST_ID_RE.search(url)
    if not match:
        raise HTTPException(status_code=400, detail="Invalid YouTube playlist URL")

    playlist_id = match.group(1)

    try:
        video_ids = await _fetch_playlist_via_innertube(playlist_id)

        if not video_ids:
            video_ids = await _fetch_playlist_via_html(playlist_id)

        if not video_ids:
            raise HTTPException(
                status_code=404,
                detail="No videos found in the playlist. It may be private or empty.",
            )

        video_urls = [f"https://www.youtube.com/watch?v={vid}" for vid in video_ids]
        return {"video_urls": video_urls, "count": len(video_urls)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error resolving playlist %s: %s", url, e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to resolve playlist: {e!s}",
        ) from e


async def _fetch_playlist_via_innertube(playlist_id: str) -> list[str]:
    """Fetch playlist videos using YouTube's innertube API (no cookies needed)."""
    payload = {
        "context": {"client": _INNERTUBE_CLIENT},
        "browseId": f"VL{playlist_id}",
    }
    proxies = get_requests_proxies()

    try:
        async with (
            aiohttp.ClientSession() as session,
            session.post(
                _INNERTUBE_API_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                proxy=proxies["http"] if proxies else None,
            ) as response,
        ):
            if response.status != 200:
                logger.warning(
                    "Innertube API returned %d for playlist %s",
                    response.status,
                    playlist_id,
                )
                return []
            data = await response.json()

        return _extract_playlist_video_ids(data)
    except Exception as e:
        logger.warning("Innertube API failed for playlist %s: %s", playlist_id, e)
        return []


async def _fetch_playlist_via_html(playlist_id: str) -> list[str]:
    """Fallback: scrape playlist page HTML with consent cookies set."""
    ua = UserAgent()
    headers = {
        "User-Agent": ua.random,
        "Accept-Language": "en-US,en;q=0.9",
    }
    cookies = {
        "CONSENT": "PENDING+999",
        "SOCS": "CAISNQgDEitib3FfaWRlbnRpdHlmcm9udGVuZHVpc2VydmVyXzIwMjMwODI5LjA3X3AxGgJlbiADGgYIgOa_pgY",
    }
    proxies = get_requests_proxies()
    playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"

    try:
        async with (
            aiohttp.ClientSession(cookies=cookies) as session,
            session.get(
                playlist_url,
                headers=headers,
                proxy=proxies["http"] if proxies else None,
            ) as response,
        ):
            if response.status != 200:
                logger.warning(
                    "HTML fallback returned %d for playlist %s",
                    response.status,
                    playlist_id,
                )
                return []
            html = await response.text()

        yt_data = _extract_yt_initial_data(html)
        if not yt_data:
            logger.warning(
                "Could not find ytInitialData in HTML for playlist %s",
                playlist_id,
            )
            return []

        return _extract_playlist_video_ids(yt_data)
    except Exception as e:
        logger.warning("HTML fallback failed for playlist %s: %s", playlist_id, e)
        return []


def _extract_yt_initial_data(html: str) -> dict | None:
    """Extract the ytInitialData JSON object embedded in a YouTube page."""
    patterns = [
        re.compile(r"var\s+ytInitialData\s*=\s*"),
        re.compile(r'window\["ytInitialData"\]\s*=\s*'),
    ]

    start = -1
    for pattern in patterns:
        match = pattern.search(html)
        if match:
            start = match.end()
            break

    if start == -1:
        return None

    depth = 0
    i = start
    while i < len(html):
        ch = html[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                break
        elif ch == '"':
            i += 1
            while i < len(html) and html[i] != '"':
                if html[i] == "\\":
                    i += 1
                i += 1
        i += 1

    try:
        return json.loads(html[start : i + 1])
    except (json.JSONDecodeError, IndexError):
        return None


def _extract_playlist_video_ids(data: dict) -> list[str]:
    """Walk the data tree and collect videoIds from playlistVideoRenderer nodes."""
    video_ids: list[str] = []
    seen: set[str] = set()

    def _walk(obj: object) -> None:
        if isinstance(obj, dict):
            if "playlistVideoRenderer" in obj:
                vid = obj["playlistVideoRenderer"].get("videoId")
                if vid and vid not in seen:
                    seen.add(vid)
                    video_ids.append(vid)
            else:
                for v in obj.values():
                    _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    _walk(data)
    return video_ids
