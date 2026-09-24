"""An audio.cpp GGUF's family, from the front of its header."""

import pytest

from modules.llm.catalog.local.engines.audiocpp.evidence import audio_family
from modules.llm.gguf import TruncatedHeaderError
from tests.unit.llm.gguf.build import BOOL, STRING, UINT32, UINT64, array, gguf, kv

pytestmark = pytest.mark.unit

# The first seven keys of audio-cpp/audio.cpp-gguf's kokoro-82m-q8_0.gguf, in
# order, read on 24 Sep 2026. Voice packs follow as 38.5 MB of metadata.
KOKORO_FRONT = [
    kv("general.architecture", STRING, "audiocpp"),
    kv("general.name", STRING, "dd3ddfaf5bbcf3ad"),
    kv("audiocpp.tensor_name_format", STRING, "native"),
    kv("audiocpp.source_format", STRING, ".gguf"),
    kv("audiocpp.weight_type", STRING, "orig"),
    kv("audiocpp.model_spec.version", UINT32, 1),
    kv("audiocpp.model_spec.family", STRING, "kokoro_tts"),
]


def test_the_family_is_read_from_the_front_of_the_header() -> None:
    """Kokoro's key order, stopped at the family."""
    assert audio_family(gguf(KOKORO_FRONT)) == "kokoro_tts"


def test_a_prefix_that_stops_before_the_family_asks_for_more() -> None:
    """The same error the shared reader raises, so a caller widens its read."""
    whole = gguf(KOKORO_FRONT)
    with pytest.raises(TruncatedHeaderError):
        audio_family(whole[: len(whole) - 4])


def test_a_file_from_another_engine_has_no_audio_family() -> None:
    """Answered at its architecture, without reading on."""
    chat = gguf(
        [
            kv("general.architecture", STRING, "qwen3"),
            kv("qwen3.context_length", UINT32, 40960),
        ]
    )
    assert audio_family(chat) is None


def test_keys_of_any_type_before_the_family_are_stepped_over() -> None:
    """Each value type has its own width; a wrong one would misread the rest."""
    header = gguf(
        [
            kv("general.architecture", STRING, "audiocpp"),
            kv("audiocpp.sample_rate", UINT64, 24000),
            kv("audiocpp.streaming", BOOL, True),
            array("audiocpp.languages", STRING, ["en-us", "fr-fr"]),
            kv("audiocpp.model_spec.family", STRING, "supertonic"),
        ]
    )
    assert audio_family(header) == "supertonic"
