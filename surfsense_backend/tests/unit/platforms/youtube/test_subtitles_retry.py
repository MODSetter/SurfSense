"""Offline tests for the subtitles blocked-IP retry (rotate-on-block, no network.

Stubs ``_build_client``/``get_requests_proxies`` so the RequestBlocked retry
path is exercised deterministically: retries only when a proxy is configured,
each attempt gets a fresh client, and the final block is re-raised.
"""

from __future__ import annotations

import pytest
from youtube_transcript_api import RequestBlocked

from app.proprietary.platforms.youtube import subtitles


class _FakeTranscript:
    is_generated = True
    language_code = "en"

    def fetch(self):
        return []  # formatters iterate snippets; empty is fine here


class _FakeTranscriptList:
    def find_transcript(self, codes):
        return _FakeTranscript()


class _FakeApi:
    """One 'IP': blocks if ``blocked``, else returns a transcript list."""

    def __init__(self, blocked: bool) -> None:
        self.blocked = blocked

    def list(self, video_id: str):
        if self.blocked:
            raise RequestBlocked(video_id)
        return _FakeTranscriptList()


def _install(monkeypatch, outcomes: list[bool], proxied: bool) -> list[_FakeApi]:
    """Each ``_build_client`` call pops the next outcome (True = blocked)."""
    built: list[_FakeApi] = []

    def fake_build():
        api = _FakeApi(outcomes[len(built)])
        built.append(api)
        return api

    monkeypatch.setattr(subtitles, "_build_client", fake_build)
    monkeypatch.setattr(
        subtitles,
        "get_requests_proxies",
        lambda: {"http": "http://p", "https": "http://p"} if proxied else None,
    )
    return built


def test_blocked_then_success_retries_with_fresh_client(monkeypatch):
    built = _install(monkeypatch, [True, True, False], proxied=True)
    track = subtitles._fetch_subtitles_sync("vid", "en", "plaintext", False)
    assert track.language == "en"
    assert len(built) == 3  # two blocked attempts + one success, each a new client


def test_all_attempts_blocked_reraises(monkeypatch):
    built = _install(monkeypatch, [True] * 10, proxied=True)
    with pytest.raises(RequestBlocked):
        subtitles._fetch_subtitles_sync("vid", "en", "plaintext", False)
    assert len(built) == subtitles._MAX_ROTATIONS + 1


def test_no_proxy_means_single_attempt(monkeypatch):
    built = _install(monkeypatch, [True] * 10, proxied=False)
    with pytest.raises(RequestBlocked):
        subtitles._fetch_subtitles_sync("vid", "en", "plaintext", False)
    assert len(built) == 1  # same egress IP; retrying would be futile
