"""Mapping a BCP-47 tag to the Kokoro pipeline that speaks it.

This map had no coverage. The video presentation agent now resolves its
narration language against the same catalog these codes are derived from, so
the mapping being total over that catalog is a property worth pinning: if a
voice is offered for a language, a pipeline must exist to speak it.

``_lang_code`` is private and tested where it lives rather than being promoted
to public API, because no caller outside the adapter needs it.
"""

from __future__ import annotations

import pytest

from app.podcasts.tts import TextToSpeechError
from app.podcasts.tts.adapters.kokoro import _lang_code
from app.podcasts.voices import TtsProvider, get_voice_catalog

pytestmark = pytest.mark.unit


def test_every_kokoro_catalog_language_maps_to_a_pipeline_code():
    voices = get_voice_catalog().for_provider(TtsProvider.KOKORO)
    assert voices, "the Kokoro roster should not be empty"
    for voice in voices:
        code = _lang_code(voice.language)
        assert len(code) == 1, (
            f"{voice.voice_id} offers {voice.language} but maps to {code!r}"
        )


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("en", "a"),
        ("en-US", "a"),
        ("en-GB", "b"),
        ("en-uk", "b"),
        ("pt-BR", "p"),
        ("zh", "z"),
        ("ja", "j"),
    ],
)
def test_a_region_subtag_selects_the_regional_pipeline(language, expected):
    assert _lang_code(language) == expected


def test_an_unmapped_language_is_rejected():
    with pytest.raises(TextToSpeechError, match="ko"):
        _lang_code("ko")
