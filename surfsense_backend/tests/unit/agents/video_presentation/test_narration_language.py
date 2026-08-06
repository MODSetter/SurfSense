"""Choosing the language and voice a presentation is narrated in.

Narration used to be hardcoded to American English: the Kokoro pipeline was
built with ``lang_code="a"`` and the voice came from a fixed provider map. A
Japanese deck was therefore read aloud by an American English voice. These
tests pin the replacement — the language the model declares wins, anything
unusable degrades, and English keeps the exact voice it had before.
"""

from __future__ import annotations

import pytest

from app.agents.video_presentation.utils import resolve_narration

pytestmark = pytest.mark.unit


def test_the_language_the_llm_declares_is_used(tts_service):
    tts_service("local/kokoro")
    assert resolve_narration("ja").language == "ja"


@pytest.mark.parametrize(
    ("declared", "expected"),
    [
        (" ZH ", "zh"),
        ("pt-BR", "pt-BR"),
        ("EN-us", "en-us"),
    ],
)
def test_a_declared_language_is_canonicalised(tts_service, declared, expected):
    """Canonicalisation is delegated to the podcast tag normaliser.

    It lowercases the primary subtag but leaves the region as written, hence
    ``EN-us`` becoming ``en-us`` rather than ``en-US``.
    """
    tts_service("local/kokoro")
    assert resolve_narration(declared).language == expected


@pytest.mark.parametrize("declared", [None, "", "   "])
def test_a_missing_language_falls_back_to_the_operator_default(
    tts_service, default_language, declared
):
    tts_service("local/kokoro")
    default_language("es")
    assert resolve_narration(declared).language == "es"


@pytest.mark.parametrize("declared", ["Japanese", "e", "🎌", "en_US", "123"])
def test_a_garbled_language_falls_back_to_the_operator_default(
    tts_service, default_language, declared
):
    tts_service("local/kokoro")
    default_language("es")
    assert resolve_narration(declared).language == "es"


def test_a_garbled_operator_default_falls_back_to_english(
    tts_service, default_language
):
    """A typo in the deployment's .env must not break rendering."""
    tts_service("local/kokoro")
    default_language("not a tag")
    assert resolve_narration(None).language == "en"


def test_a_language_the_provider_cannot_speak_falls_back_to_english(
    tts_service, default_language
):
    """Kokoro has no Korean voice, so Korean is not a usable narration language."""
    tts_service("local/kokoro")
    default_language("en")
    assert resolve_narration("ko").language == "en"


def test_a_wildcard_provider_accepts_any_language(tts_service):
    """Hosted voices follow the input text, so they are not language-limited."""
    tts_service("openai/tts-1")
    assert resolve_narration("ko").language == "ko"


def test_an_unconfigured_tts_service_is_rejected(tts_service):
    tts_service(None)
    with pytest.raises(ValueError, match="TTS_SERVICE"):
        resolve_narration("en")


@pytest.mark.parametrize(
    ("service", "expected_voice"),
    [
        ("local/kokoro", "af_heart"),
        ("openai/tts-1", "alloy"),
        ("azure/neural", "alloy"),
        ("vertex_ai/studio", {"languageCode": "en-US", "name": "en-US-Studio-O"}),
    ],
)
def test_english_keeps_the_voice_it_had_before_this_change(
    tts_service, service, expected_voice
):
    """The literal values the deleted provider map returned.

    The catalog lists ``am_adam`` ahead of ``af_heart``, so without seeding the
    previous voice as preferred every existing English presentation would be
    silently re-cast. This is the no-regression guard for that.
    """
    tts_service(service)
    assert resolve_narration("en").voice == expected_voice


def test_japanese_selects_a_japanese_kokoro_voice(tts_service):
    """Kokoro voice names are prefixed by their language letter."""
    tts_service("local/kokoro")
    assert resolve_narration("ja").voice.startswith("j")


def test_chinese_selects_a_chinese_kokoro_voice(tts_service):
    tts_service("local/kokoro")
    assert resolve_narration("zh").voice.startswith("z")


def test_a_wildcard_provider_keeps_one_voice_for_every_language(tts_service):
    tts_service("openai/tts-1")
    assert resolve_narration("ja").voice == "alloy"
