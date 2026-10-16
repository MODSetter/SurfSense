import pytest

from shared.config import LLMSettings

pytestmark = pytest.mark.unit


def test_reads_the_speech_recognition_server_electron_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Electron gives the API alone this address (sidecars/python.ts)."""
    monkeypatch.setenv(
        "SURFSENSE_LOCAL_TRANSCRIPTION_BASE_URL", "http://127.0.0.1:9997"
    )
    assert LLMSettings().transcription_base_url == "http://127.0.0.1:9997"


def test_names_no_speech_recognition_server_unless_told(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No audio.cpp staged, or a worker's environment: there is none to call."""
    monkeypatch.delenv("SURFSENSE_LOCAL_TRANSCRIPTION_BASE_URL", raising=False)
    assert LLMSettings().transcription_base_url is None
