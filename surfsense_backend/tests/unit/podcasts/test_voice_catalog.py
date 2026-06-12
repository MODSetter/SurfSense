"""The voice catalog and provider identification.

The catalog is the single source of truth for which voices exist; resolution,
the API picker, and the renderer all depend on its lookups behaving correctly.
These tests build a small catalog of their own so they assert on the lookup
behavior, not on which specific voices ship.
"""

from __future__ import annotations

import pytest

from app.podcasts.voices import (
    ANY_LANGUAGE,
    CatalogVoice,
    TtsProvider,
    VoiceCatalog,
    VoiceGender,
    provider_from_service,
)

pytestmark = pytest.mark.unit


def _voice(
    voice_id: str,
    *,
    provider: TtsProvider = TtsProvider.KOKORO,
    language: str = "en-US",
    gender: VoiceGender = VoiceGender.MALE,
) -> CatalogVoice:
    return CatalogVoice(
        voice_id=voice_id,
        provider=provider,
        language=language,
        display_name=voice_id,
        gender=gender,
        native_ref=voice_id,
    )


def test_for_provider_returns_only_that_providers_voices():
    catalog = VoiceCatalog(
        [
            _voice("k1", provider=TtsProvider.KOKORO),
            _voice("o1", provider=TtsProvider.OPENAI),
        ]
    )
    assert [v.voice_id for v in catalog.for_provider(TtsProvider.KOKORO)] == ["k1"]


def test_for_language_matches_on_the_primary_subtag():
    """A request for 'en' should match an 'en-US' voice (region-insensitive)."""
    catalog = VoiceCatalog([_voice("k1", language="en-US")])
    assert [v.voice_id for v in catalog.for_language(TtsProvider.KOKORO, "en")] == [
        "k1"
    ]


def test_for_language_excludes_other_languages():
    catalog = VoiceCatalog([_voice("k1", language="en-US")])
    assert catalog.for_language(TtsProvider.KOKORO, "fr") == []


def test_an_any_language_voice_speaks_every_language():
    """Provider-agnostic voices (e.g. OpenAI) match whatever the text is in."""
    voice = _voice("o1", provider=TtsProvider.OPENAI, language=ANY_LANGUAGE)
    assert voice.speaks("ja")
    assert voice.speaks("pt-BR")


def test_supports_language_reports_availability():
    catalog = VoiceCatalog([_voice("k1", language="en-US")])
    assert catalog.supports_language(TtsProvider.KOKORO, "en")
    assert not catalog.supports_language(TtsProvider.KOKORO, "de")


def test_offerable_languages_for_a_concrete_roster_are_its_tags_only():
    """A provider whose voices are language-bound offers exactly those tags."""
    catalog = VoiceCatalog(
        [
            _voice("k1", language="en-US"),
            _voice("k2", language="fr"),
            _voice("k3", language="fr"),
        ]
    )

    offering = catalog.offerable_languages(TtsProvider.KOKORO)

    assert offering.languages == ["en-US", "fr"]
    assert offering.allows_custom is False


def test_a_wildcard_roster_offers_the_curated_languages_and_custom_entry():
    """Voices that speak anything can't enumerate languages themselves, so the
    catalog offers the curated common list and invites free entry."""
    catalog = VoiceCatalog(
        [_voice("o1", provider=TtsProvider.OPENAI, language=ANY_LANGUAGE)]
    )

    offering = catalog.offerable_languages(TtsProvider.OPENAI)

    assert {"en", "fr", "sw", "hi", "zh"} <= set(offering.languages)
    assert offering.allows_custom is True


def test_a_mixed_roster_offers_the_union_of_concrete_and_curated():
    catalog = VoiceCatalog(
        [
            _voice("v1", provider=TtsProvider.VERTEX_AI, language="en-GB"),
            _voice("v2", provider=TtsProvider.VERTEX_AI, language=ANY_LANGUAGE),
        ]
    )

    offering = catalog.offerable_languages(TtsProvider.VERTEX_AI)

    assert "en-GB" in offering.languages
    assert "fr" in offering.languages
    assert offering.allows_custom is True


def test_a_provider_with_no_voices_offers_nothing():
    catalog = VoiceCatalog([_voice("k1")])

    offering = catalog.offerable_languages(TtsProvider.OPENAI)

    assert offering.languages == []
    assert offering.allows_custom is False


def test_get_raises_for_an_unknown_voice():
    catalog = VoiceCatalog([_voice("k1")])
    with pytest.raises(KeyError):
        catalog.get("nope")


def test_a_catalog_rejects_duplicate_voice_ids():
    """Stored ids must be unique so a brief's voice_id resolves unambiguously."""
    with pytest.raises(ValueError):
        VoiceCatalog([_voice("dup"), _voice("dup")])


@pytest.mark.parametrize(
    ("service", "expected"),
    [
        ("openai/tts-1", TtsProvider.OPENAI),
        ("azure/neural", TtsProvider.AZURE),
        ("vertex_ai/some-model", TtsProvider.VERTEX_AI),
        ("local/kokoro", TtsProvider.KOKORO),
    ],
)
def test_provider_is_identified_from_the_config_string(service, expected):
    assert provider_from_service(service) == expected


def test_unknown_provider_prefix_is_rejected():
    with pytest.raises(ValueError):
        provider_from_service("madeup/model")
