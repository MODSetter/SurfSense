"""Audible voice previews for the brief gate's voice picker.

A user choosing voices should hear them, not guess from names. The endpoint
synthesises a short sample for a catalog voice and caches it on disk so each
voice is paid for at most once per process lifetime. Unknown voices and voices
of an inactive provider are 404; no configured TTS is 503.
"""

from __future__ import annotations

import pytest

from app.config import config as app_config

from .conftest import FakeTextToSpeech

pytestmark = pytest.mark.integration

BASE = "/api/v1/podcasts"


@pytest.fixture
def preview_tts(monkeypatch, tmp_path) -> FakeTextToSpeech:
    """Route preview synthesis to the fake provider and an isolated cache."""
    provider = FakeTextToSpeech()
    monkeypatch.setattr("app.podcasts.api.routes.get_text_to_speech", lambda: provider)
    monkeypatch.setattr("app.podcasts.voices.preview.PREVIEW_CACHE_ROOT", tmp_path)
    return provider


async def test_preview_returns_playable_audio_for_a_catalog_voice(client, preview_tts):
    resp = await client.get(f"{BASE}/voices/openai:alloy/preview")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/mpeg"
    assert resp.content == b"segment-audio"


async def test_preview_is_synthesised_once_then_served_from_cache(client, preview_tts):
    first = await client.get(f"{BASE}/voices/openai:alloy/preview")
    second = await client.get(f"{BASE}/voices/openai:alloy/preview")

    assert first.status_code == second.status_code == 200
    assert second.content == first.content
    assert len(preview_tts.requests) == 1


async def test_preview_unknown_voice_is_404(client, preview_tts):
    resp = await client.get(f"{BASE}/voices/openai:nope/preview")

    assert resp.status_code == 404
    assert preview_tts.requests == []


async def test_preview_voice_of_inactive_provider_is_404(client, preview_tts):
    # The active provider is OpenAI (pinned in conftest); a Kokoro voice exists
    # in the catalog but cannot be heard through the configured provider.
    resp = await client.get(f"{BASE}/voices/kokoro:af_heart/preview")

    assert resp.status_code == 404
    assert preview_tts.requests == []


async def test_preview_without_tts_provider_is_503(client, preview_tts, monkeypatch):
    monkeypatch.setattr(app_config, "TTS_SERVICE", None)

    resp = await client.get(f"{BASE}/voices/openai:alloy/preview")

    assert resp.status_code == 503
