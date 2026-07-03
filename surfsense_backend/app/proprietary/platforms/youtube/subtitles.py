"""Subtitle download via ``youtube-transcript-api``, shaped to Apify ``subtitles[]``.

Uses the library's built-in formatters (no hand-rolled srt/vtt conversion). The
transcript API has no XML formatter, so ``xml`` falls back to the raw snippet
data.
"""

from __future__ import annotations

import asyncio
import logging

from fake_useragent import UserAgent
from requests import Session
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import (
    SRTFormatter,
    TextFormatter,
    WebVTTFormatter,
)

from app.utils.proxy import get_requests_proxies

from .schemas import SubtitleTrack

logger = logging.getLogger(__name__)

_FORMATTERS = {
    "srt": SRTFormatter,
    "vtt": WebVTTFormatter,
    "plaintext": TextFormatter,
}


def _build_client() -> YouTubeTranscriptApi:
    http_client = Session()
    http_client.headers.update({"User-Agent": UserAgent().random})
    proxies = get_requests_proxies()
    if proxies:
        http_client.proxies.update(proxies)
    return YouTubeTranscriptApi(http_client=http_client)


def _select_transcript(transcript_list, language: str, prefer_generated: bool):
    """Pick a transcript honoring language + generated/manual preference."""
    # ``any`` means take whatever the video offers first.
    if language == "any":
        return next(iter(transcript_list))

    codes = [language]
    if prefer_generated:
        try:
            return transcript_list.find_generated_transcript(codes)
        except Exception:
            return transcript_list.find_transcript(codes)
    return transcript_list.find_transcript(codes)


def _fetch_subtitles_sync(
    video_id: str, language: str, fmt: str, prefer_generated: bool
):
    api = _build_client()
    transcript_list = api.list(video_id)
    transcript = _select_transcript(transcript_list, language, prefer_generated)
    fetched = transcript.fetch()

    if fmt == "xml":
        # No XML formatter in the library; emit the raw snippet data as text.
        body = str(fetched.to_raw_data())
    else:
        formatter_cls = _FORMATTERS.get(fmt, SRTFormatter)
        body = formatter_cls().format_transcript(fetched)

    return SubtitleTrack(
        srtUrl=None,
        type="auto_generated" if transcript.is_generated else "user_generated",
        language=transcript.language_code,
        srt=body,
    )


async def fetch_subtitles(
    video_id: str,
    *,
    language: str = "en",
    fmt: str = "srt",
    prefer_generated: bool = False,
) -> list[SubtitleTrack] | None:
    """Return the Apify ``subtitles[]`` list for a video, or ``None`` if none.

    Runs the blocking transcript API in a worker thread to stay async-friendly.
    """
    try:
        track = await asyncio.to_thread(
            _fetch_subtitles_sync, video_id, language, fmt, prefer_generated
        )
        return [track]
    except Exception as e:
        logger.info("No subtitles for video %s (%s): %s", video_id, language, e)
        return None
