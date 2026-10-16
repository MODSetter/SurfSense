"""The native subtitles path (ANDROID /player, then the track) and its fallback.

No network: ``post_innertube`` and ``fetch_html`` in ``subtitles`` are replaced.
``timedtext_kCc8FmEb1nY.xml`` is the first cues of a live capture; the player
fixture mirrors the live ANDROID answer's caption block (its tracks and kinds,
URL signatures dropped).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
import requests
from youtube_transcript_api import FetchedTranscript
from youtube_transcript_api._transcripts import _TranscriptParser
from youtube_transcript_api.formatters import SRTFormatter

from proprietary.scraping import sessions
from proprietary.youtube import subtitles
from proprietary.youtube.innertube import INNERTUBE_PLAYER_URL
from proprietary.youtube.schemas import SubtitleTrack

_FIXTURES = Path(__file__).parent / "fixtures"
_VIDEO = "kCc8FmEb1nY"
_BOT = {
    "playabilityStatus": {
        "status": "LOGIN_REQUIRED",
        "reason": "Sign in to confirm you’re not a bot",  # noqa: RUF001
    }
}


def player() -> dict[str, Any]:
    return json.loads(
        (_FIXTURES / f"player_android_{_VIDEO}.json").read_text(encoding="utf-8")
    )


def timedtext() -> str:
    return (_FIXTURES / f"timedtext_{_VIDEO}.xml").read_text(encoding="utf-8")


def track(code: str, *, asr: bool) -> dict[str, Any]:
    return {"baseUrl": f"u/{code}/{asr}", "languageCode": code} | (
        {"kind": "asr"} if asr else {}
    )


class FakeYouTube:
    def __init__(self, players: list[dict | None]) -> None:
        self.players = players
        self.posts: list[tuple[str, dict]] = []
        self.gets: list[str] = []

    async def post_innertube(self, base_url: str, payload: dict, **kw: Any):
        self.posts.append((base_url, payload))
        return self.players.pop(0)

    async def fetch_html(self, url: str, **kw: Any) -> str | None:
        self.gets.append(url)
        return timedtext()


@pytest.fixture
def library(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The youtube-transcript-api fallback, recording the videos it was asked for."""
    asked: list[str] = []

    def fetch(video_id: str, language: str, fmt: str, prefer_generated: bool):
        asked.append(video_id)
        return SubtitleTrack(type="user_generated", language="en", srt="library")

    monkeypatch.setattr(subtitles, "_fetch_subtitles_sync", fetch)
    return asked


def install(monkeypatch: pytest.MonkeyPatch, players: list) -> FakeYouTube:
    fake = FakeYouTube(players)
    monkeypatch.setattr(subtitles, "post_innertube", fake.post_innertube)
    monkeypatch.setattr(subtitles, "fetch_html", fake.fetch_html)
    return fake


# --- track choice: the library's semantics over raw captionTracks -------------


def test_manual_tracks_come_before_generated_ones() -> None:
    tracks = [track("en", asr=True), track("en", asr=False)]

    assert subtitles._pick_track(tracks, "en", False) == tracks[1]
    assert subtitles._pick_track(tracks, "en", True) == tracks[0]


def test_prefer_generated_still_takes_a_manual_track_when_alone() -> None:
    tracks = [track("en", asr=False)]

    assert subtitles._pick_track(tracks, "en", True) == tracks[0]


def test_any_language_takes_the_first_manual_track() -> None:
    tracks = [track("de", asr=True), track("fr", asr=False)]

    assert subtitles._pick_track(tracks, "any", False) == tracks[1]


def test_a_missing_language_has_no_track() -> None:
    assert subtitles._pick_track([track("en", asr=True)], "fr", False) is None


# --- the native path ------------------------------------------------------------


async def test_native_subtitles_match_the_library_formatting(
    monkeypatch: pytest.MonkeyPatch, library: list[str]
) -> None:
    fake = install(monkeypatch, [player()])

    tracks = await subtitles.fetch_subtitles(_VIDEO)

    expected = SRTFormatter().format_transcript(
        FetchedTranscript(
            snippets=_TranscriptParser().parse(timedtext()),
            video_id=_VIDEO,
            language="English (auto-generated)",
            language_code="en",
            is_generated=True,
        )
    )
    assert tracks == [SubtitleTrack(type="auto_generated", language="en", srt=expected)]
    assert expected.startswith("1\n00:00:00,199 --> 00:00:02,520\nhi everyone")
    url, payload = fake.posts[0]
    assert url == INNERTUBE_PLAYER_URL
    assert payload["context"]["client"]["clientName"] == "ANDROID"
    assert payload["videoId"] == _VIDEO
    # The library's request: the plain XML, not srv3.
    assert "fmt=srv3" not in fake.gets[0]
    assert "lang=en" in fake.gets[0]
    assert library == []


async def test_a_bot_check_rotates_the_exit_and_asks_again(
    monkeypatch: pytest.MonkeyPatch, library: list[str]
) -> None:
    fake = install(monkeypatch, [_BOT, player()])

    async with sessions.bound("youtube") as h:
        tracks = await subtitles.fetch_subtitles(_VIDEO, fmt="plaintext")

    assert tracks is not None and tracks[0].srt.startswith("hi everyone")
    assert h.rotations == 1  # the second ask goes out on a fresh exit
    assert len(fake.posts) == 2
    assert library == []


async def test_one_bot_checked_exit_costs_one_rotation_across_items(
    monkeypatch: pytest.MonkeyPatch, library: list[str]
) -> None:
    fake = install(monkeypatch, [])
    asked_on: list[int] = []  # the holder's rotation count at each ask

    async def post_innertube(base_url: str, payload: dict, **kw: Any):
        asked_on.append(h.rotations)
        asks = len(asked_on)
        if asks <= 3:  # three items asked on one exit, refused one by one
            await asyncio.sleep(0.03 * asks)
            return _BOT
        return player()

    monkeypatch.setattr(subtitles, "post_innertube", post_innertube)

    async with sessions.bound("youtube") as h:
        tracks = await asyncio.gather(
            *(subtitles.fetch_subtitles(_VIDEO) for _ in range(3))
        )

    assert all(t is not None for t in tracks)
    assert h.rotations == 1
    assert asked_on == [0, 0, 0, 1, 1, 1]  # every retry on the one new exit
    assert len(fake.gets) == 3
    assert library == []


async def test_a_bot_check_twice_falls_back_to_the_library(
    monkeypatch: pytest.MonkeyPatch, library: list[str]
) -> None:
    install(monkeypatch, [_BOT, _BOT])

    tracks = await subtitles.fetch_subtitles(_VIDEO)

    assert [t.srt for t in tracks or []] == ["library"]
    assert library == [_VIDEO]


async def test_an_unanswered_player_falls_back_to_the_library(
    monkeypatch: pytest.MonkeyPatch, library: list[str]
) -> None:
    install(monkeypatch, [None])

    tracks = await subtitles.fetch_subtitles(_VIDEO)

    assert [t.srt for t in tracks or []] == ["library"]


async def test_a_track_needing_a_po_token_falls_back_to_the_library(
    monkeypatch: pytest.MonkeyPatch, library: list[str]
) -> None:
    answer = player()
    for t in answer["captions"]["playerCaptionsTracklistRenderer"]["captionTracks"]:
        t["baseUrl"] += "&exp=xpe"
    fake = install(monkeypatch, [answer])

    tracks = await subtitles.fetch_subtitles(_VIDEO)

    assert [t.srt for t in tracks or []] == ["library"]
    assert fake.gets == []


async def test_no_track_in_the_language_is_no_subtitles_without_a_fallback(
    monkeypatch: pytest.MonkeyPatch, library: list[str]
) -> None:
    install(monkeypatch, [player()])

    assert await subtitles.fetch_subtitles(_VIDEO, language="ja") is None
    assert library == []


async def test_turning_native_off_goes_straight_to_the_library(
    monkeypatch: pytest.MonkeyPatch, library: list[str]
) -> None:
    fake = install(monkeypatch, [player()])
    monkeypatch.setattr(subtitles, "_NATIVE", False)

    tracks = await subtitles.fetch_subtitles(_VIDEO)

    assert [t.srt for t in tracks or []] == ["library"]
    assert fake.posts == []


def test_the_library_client_never_sends_without_a_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, Any]] = []
    monkeypatch.setattr(
        requests.Session, "request", lambda self, method, url, **kw: sent.append(kw)
    )
    session = subtitles._TimeoutSession()

    session.get("https://www.youtube.com/watch?v=x")
    session.post("https://www.youtube.com/youtubei/v1/player", timeout=3)

    assert [kw["timeout"] for kw in sent] == [subtitles._LIBRARY_TIMEOUT, 3]
