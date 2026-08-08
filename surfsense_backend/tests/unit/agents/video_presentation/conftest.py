"""Fixtures for the video presentation agent's unit tests.

``Config`` reads the environment once at import, so a test that sets
``os.environ`` changes nothing. Every knob here is therefore set on the config
singleton itself, which is also how the rest of the suite does it.
"""

from __future__ import annotations

import pytest

from app.config import config


@pytest.fixture
def tts_service(monkeypatch):
    """Point the agent at a TTS provider for the duration of one test."""

    def _set(service: str | None = "local/kokoro") -> None:
        monkeypatch.setattr(config, "TTS_SERVICE", service)

    return _set


@pytest.fixture
def default_language(monkeypatch):
    """Set the operator's fallback narration language."""

    def _set(language: str) -> None:
        monkeypatch.setattr(config, "VIDEO_PRESENTATION_DEFAULT_LANGUAGE", language)

    return _set
