"""Default language and voice selection for a fresh brief.

Resolution is what lets most briefs need no edits: it proposes a sensible
language and a distinct voice per speaker. These tests state the policy
("detected wins, else last-used, else English"; "two speakers should sound
like two people") through the public resolver functions and the real catalog.
"""

from __future__ import annotations

import pytest

from app.podcasts.resolution import (
    DEFAULT_LANGUAGE,
    LanguageContext,
    VoiceResolutionError,
    resolve_language,
    resolve_voices,
)
from app.podcasts.voices import TtsProvider, get_voice_catalog

pytestmark = pytest.mark.unit


def test_detected_language_is_preferred_over_everything():
    context = LanguageContext(detected="es", last_used="fr")
    assert resolve_language(context) == "es"


def test_falls_back_to_last_used_when_nothing_detected():
    context = LanguageContext(detected=None, last_used="fr")
    assert resolve_language(context) == "fr"


def test_first_time_user_with_no_signal_gets_the_default():
    assert resolve_language(LanguageContext()) == DEFAULT_LANGUAGE


def test_two_speakers_get_distinct_voices():
    """A two-speaker episode should not voice both with the same person."""
    catalog = get_voice_catalog()
    voices = resolve_voices(
        catalog=catalog, provider=TtsProvider.KOKORO, language="en", speaker_count=2
    )
    assert len(voices) == 2
    assert voices[0].voice_id != voices[1].voice_id


def test_a_users_preferred_voice_is_reused_when_still_valid():
    catalog = get_voice_catalog()
    voices = resolve_voices(
        catalog=catalog,
        provider=TtsProvider.KOKORO,
        language="en",
        speaker_count=2,
        preferred=["kokoro:af_bella"],
    )
    assert voices[0].voice_id == "kokoro:af_bella"


def test_a_preferred_voice_invalid_for_the_language_is_replaced():
    """A stale preference (wrong provider/language) is silently dropped."""
    catalog = get_voice_catalog()
    voices = resolve_voices(
        catalog=catalog,
        provider=TtsProvider.KOKORO,
        language="en",
        speaker_count=1,
        preferred=["kokoro:does-not-exist"],
    )
    assert voices[0].voice_id in {v.voice_id for v in catalog.for_provider(TtsProvider.KOKORO)}


def test_resolution_fails_when_no_voice_speaks_the_language():
    """If a provider can't speak the language at all, that is surfaced loudly."""
    catalog = get_voice_catalog()
    with pytest.raises(VoiceResolutionError):
        resolve_voices(
            catalog=catalog,
            provider=TtsProvider.KOKORO,
            language="xx",
            speaker_count=1,
        )


def test_every_speaker_is_assigned_even_when_voices_run_out():
    """With one available voice, both speakers still get one rather than failing."""
    catalog = get_voice_catalog()
    voices = resolve_voices(
        catalog=catalog, provider=TtsProvider.KOKORO, language="fr", speaker_count=2
    )
    assert len(voices) == 2


def test_speaker_count_must_be_positive():
    catalog = get_voice_catalog()
    with pytest.raises(ValueError):
        resolve_voices(
            catalog=catalog, provider=TtsProvider.KOKORO, language="en", speaker_count=0
        )
