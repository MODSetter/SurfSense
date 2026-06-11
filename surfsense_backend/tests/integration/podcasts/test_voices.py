"""GET /podcasts/voices: the active provider's catalog, or 503 if unconfigured.

The brief UI needs the voices the configured TTS provider offers; with no
provider configured there is nothing to choose from, which is a 503 rather than
an empty list.
"""

import pytest

from app.config import config as app_config

pytestmark = pytest.mark.integration

BASE = "/api/v1/podcasts"


async def test_voices_returns_the_active_providers_catalog(client):
    resp = await client.get(f"{BASE}/voices")

    assert resp.status_code == 200
    voices = resp.json()
    assert voices  # openai/tts-1 offers voices
    assert {"voice_id", "display_name", "language", "gender"} <= voices[0].keys()


async def test_voices_503_when_no_tts_configured(client, monkeypatch):
    monkeypatch.setattr(app_config, "TTS_SERVICE", "")

    resp = await client.get(f"{BASE}/voices")

    assert resp.status_code == 503
