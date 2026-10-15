"""Subtitle download, shaped to Apify ``subtitles[]``.

The native path asks InnerTube's ANDROID ``/player`` for the caption tracks and
GETs the chosen track, both on the job's warm proxy holder (about 0.5 s on a
kept connection). ``youtube-transcript-api`` stays as the fallback: on its own
requests session it downloads the watch page again and took 3-11 s, with
BOT_DETECTED retries. Both shape the track with the library's parser and
formatters (no hand-rolled srt/vtt conversion). The transcript API has no XML
formatter, so ``xml`` falls back to the raw snippet data.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from fake_useragent import UserAgent
from requests import Session
from youtube_transcript_api import (
    FetchedTranscript,
    RequestBlocked,
    YouTubeTranscriptApi,
)
from youtube_transcript_api._transcripts import _TranscriptParser
from youtube_transcript_api.formatters import (
    SRTFormatter,
    TextFormatter,
    WebVTTFormatter,
)

from proprietary.scraping import sessions
from proprietary.scraping.proxy import get_requests_proxies

from .innertube import INNERTUBE_PLAYER_URL, fetch_html, post_innertube
from .schemas import SubtitleTrack

logger = logging.getLogger(__name__)

_FORMATTERS = {
    "srt": SRTFormatter,
    "vtt": WebVTTFormatter,
    "plaintext": TextFormatter,
}

# Blocked-IP retries, mirroring innertube's rotate-on-block. Each retry builds a
# fresh Session (new TCP connection), which draws a new exit IP on a rotating
# proxy gateway. Without a proxy we don't retry - the egress IP can't change.
_MAX_ROTATIONS = 3

# YOUTUBE_NATIVE_SUBTITLES=0 goes straight to the library, as before.
_NATIVE = os.getenv("YOUTUBE_NATIVE_SUBTITLES", "1") != "0"
# The client youtube-transcript-api uses: its caption URLs need no PO token,
# where the web player's carry exp=xpe.
_ANDROID_CONTEXT = {"client": {"clientName": "ANDROID", "clientVersion": "20.10.38"}}
_BOT_DETECTED = "Sign in to confirm you’re not a bot"  # noqa: RUF001 - YouTube's text
_NATIVE_TRIES = 2


class _NoAnswerError(Exception):
    """The native path could not tell; the library gets its turn."""


# The library sends without a timeout: a stalled proxy would hang its worker
# thread, which no cancel reaches, with no progress reported meanwhile.
_LIBRARY_TIMEOUT = (4, 12)


class _TimeoutSession(Session):
    def request(self, method: str | bytes, url: str | bytes, **kwargs: Any):
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = _LIBRARY_TIMEOUT
        return super().request(method, url, **kwargs)


def _build_client() -> YouTubeTranscriptApi:
    http_client = _TimeoutSession()
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


def _pick_track(
    tracks: list[dict[str, Any]], language: str, prefer_generated: bool
) -> dict[str, Any] | None:
    """:func:`_select_transcript` over raw ``captionTracks`` (``kind == "asr"`` is generated)."""
    manual: dict[str, dict[str, Any]] = {}
    generated: dict[str, dict[str, Any]] = {}
    for track in tracks:
        if isinstance(track, dict) and track.get("baseUrl"):
            kind = generated if track.get("kind") == "asr" else manual
            kind[track.get("languageCode")] = track
    if language == "any":
        return next(iter([*manual.values(), *generated.values()]), None)
    for kind in (generated, manual) if prefer_generated else (manual, generated):
        if language in kind:
            return kind[language]
    return None


def _shape(
    fetched: FetchedTranscript, fmt: str, *, generated: bool, language: str
) -> SubtitleTrack:
    if fmt == "xml":
        # No XML formatter in the library; emit the raw snippet data as text.
        body = str(fetched.to_raw_data())
    else:
        formatter_cls = _FORMATTERS.get(fmt, SRTFormatter)
        body = formatter_cls().format_transcript(fetched)
    return SubtitleTrack(
        srtUrl=None,
        type="auto_generated" if generated else "user_generated",
        language=language,
        srt=body,
    )


def _native_shape(
    xml: str, track: dict[str, Any], video_id: str, fmt: str
) -> SubtitleTrack:
    runs = (track.get("name") or {}).get("runs") or [{}]
    code, generated = track.get("languageCode"), track.get("kind") == "asr"
    fetched = FetchedTranscript(
        snippets=_TranscriptParser().parse(xml),
        video_id=video_id,
        language=runs[0].get("text") or code,
        language_code=code,
        is_generated=generated,
    )
    return _shape(fetched, fmt, generated=generated, language=code)


async def _native_subtitles(
    video_id: str, language: str, fmt: str, prefer_generated: bool
) -> SubtitleTrack | None:
    """The track over InnerTube, ``None`` when the video has no such track.

    Raises :class:`_NoAnswerError` when blocked or unanswered.
    """
    payload = {"context": _ANDROID_CONTEXT, "videoId": video_id}
    h = sessions.current()
    for _ in range(_NATIVE_TRIES):
        seen = h.rotations if h is not None else 0  # other items may share h
        data = await post_innertube(INNERTUBE_PLAYER_URL, payload)
        if data is None:
            raise _NoAnswerError("player unanswered")
        status = data.get("playabilityStatus") or {}
        if status.get("reason") != _BOT_DETECTED:
            break
        # A 200 that is a block: this exit is refused. When a sibling item has
        # rotated since, the retry already goes out on a fresh exit.
        logger.warning("[youtube] player BOT_DETECTED for %s", video_id)
        if h is not None:
            await h.rotate("bot_detected", seen=seen)
    else:
        raise _NoAnswerError("player blocked")
    if status.get("status") not in (None, "OK"):
        return None  # unplayable or age-restricted: the library would refuse too
    captions = (data.get("captions") or {}).get("playerCaptionsTracklistRenderer")
    track = _pick_track(
        (captions or {}).get("captionTracks") or [], language, prefer_generated
    )
    if track is None:
        return None
    url = track["baseUrl"].replace("&fmt=srv3", "")
    if "&exp=xpe" in url:
        raise _NoAnswerError("PO token required")
    xml = await fetch_html(url, stage="timedtext")
    if not xml:
        raise _NoAnswerError("track unanswered")
    return await asyncio.to_thread(_native_shape, xml, track, video_id, fmt)


def _fetch_subtitles_sync(
    video_id: str, language: str, fmt: str, prefer_generated: bool
):
    attempts = (_MAX_ROTATIONS + 1) if get_requests_proxies() else 1
    for attempt in range(attempts):
        api = _build_client()
        try:
            transcript_list = api.list(video_id)
            transcript = _select_transcript(transcript_list, language, prefer_generated)
            fetched = transcript.fetch()
            break
        except RequestBlocked:  # covers IpBlocked; rotate to a fresh exit IP
            if attempt == attempts - 1:
                raise
            logger.info(
                "Transcript request blocked for %s; retrying on a fresh proxy "
                "connection (attempt %d/%d)",
                video_id,
                attempt + 2,
                attempts,
            )
    return _shape(
        fetched,
        fmt,
        generated=transcript.is_generated,
        language=transcript.language_code,
    )


async def fetch_subtitles(
    video_id: str,
    *,
    language: str = "en",
    fmt: str = "srt",
    prefer_generated: bool = False,
) -> list[SubtitleTrack] | None:
    """Return the Apify ``subtitles[]`` list for a video, or ``None`` if none.

    Native first; the blocking transcript API, in a worker thread, when the
    native path cannot answer.
    """
    if _NATIVE:
        try:
            track = await _native_subtitles(video_id, language, fmt, prefer_generated)
            return [track] if track is not None else None
        except Exception as e:  # any surprise in the native path: the library
            logger.info("Native subtitles for %s fell back: %s", video_id, e)
    try:
        track = await asyncio.to_thread(
            _fetch_subtitles_sync, video_id, language, fmt, prefer_generated
        )
        return [track]
    except Exception as e:
        logger.info("No subtitles for video %s (%s): %s", video_id, language, e)
        return None
