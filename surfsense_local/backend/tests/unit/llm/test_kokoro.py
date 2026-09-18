import asyncio

import pytest

from modules.llm.providers.kokoro import provider as kokoro
from modules.llm.providers.protocols import SpokenTurn


def test_every_voice_names_its_language_and_english_stays_first() -> None:
    """The brief can group voices by language; the default language is en-US."""
    voices = kokoro.KokoroProvider().voices()
    languages = {voice.language for voice in voices}
    assert {"en-US", "en-GB", "es", "fr", "hi", "it", "pt-BR"} <= languages
    assert voices[0].language == "en-US"
    assert len({voice.id for voice in voices}) == len(voices)


def test_a_turn_is_spoken_in_its_voices_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The phonemiser gets the espeak code of the voice, not a fixed en-us."""
    spoken: list[tuple[str, str]] = []

    class FakeEngine:
        def create(self, text: str, *, voice: str, speed: float, lang: str):
            spoken.append((voice, lang))
            return [0.0] * 10, kokoro.SAMPLE_RATE

    monkeypatch.setattr(kokoro, "_engine", FakeEngine)
    turns = [SpokenTurn("pf_dora", "Olá"), SpokenTurn("bm_george", "Hello")]
    audio = asyncio.run(kokoro.KokoroProvider().synthesize(turns))

    assert spoken == [("pf_dora", "pt-br"), ("bm_george", "en-gb")]
    assert audio.media_type == "audio/wav"
