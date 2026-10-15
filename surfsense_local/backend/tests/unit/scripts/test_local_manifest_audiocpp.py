"""An audio model's manifest entry: its builds from one folder of a shared repo,
its family from the file, and its voices from the reviewed entry.
"""

import pytest
from local_manifest.audiocpp.assemble import entry_for, pinned_builds
from local_manifest.audiocpp.entry import AudioEntry
from local_manifest.recorded import RepoAtRevision
from local_manifest.unreadable import UnreadableBuildError

from modules.llm.catalog.local.listed_file import ListedFile
from modules.llm.catalog.local.manifest import SCHEMA_VERSION, LocalManifest

pytestmark = pytest.mark.unit

REV = "0a104324546d2622985e3c676a4b5550cc772127"
ENTRY = AudioEntry(
    id="supertonic-3",
    name="Supertonic 3",
    family="Supertonic",
    publisher="Supertone",
    description="Ten voices, each in 31 languages.",
    license="openrail",
    source_repo="Supertone/supertonic-3",
    repo="audio-cpp/audio.cpp-gguf",
    folder="Supertonic-3-GGUF",
    builds=("F16", "orig"),
    audio={
        "origin": "Supertone/supertonic-3 model card",
        "sample_rate": 44100,
        "peak_mb": 454,
        "languages": ["en", "fr"],
        "voices": [
            {"id": "M1", "label": "M1", "gender": "male"},
            {"id": "F1", "label": "F1", "gender": "female"},
        ],
    },
)
# audio-cpp/audio.cpp-gguf at REV, read on 24 Sep 2026. Its q8_0 file has the
# orig file's hash: the same bytes under a quantized name.
ORIG = "af814486a0bc9513fb36afabd9b1155ad14fb2c36a107ac6ffe62ea9adafb662"
SNAPSHOT = RepoAtRevision(
    ENTRY.repo,
    REV,
    "text-to-speech",
    (
        ListedFile(
            "Kokoro-82M-GGUF/kokoro-82m-q8_0.gguf",
            189549408,
            "5d800fd204029302c10313daeafdb31c875c7c29ae31974d0d156cc7f512d1d0",
        ),
        ListedFile(
            "Supertonic-3-GGUF/supertonic-3-f16.gguf",
            312784196,
            "b312b57797d40ac5c09d915893dbdbaf6405b7dc043f544776c5c95712dff88c",
        ),
        ListedFile("Supertonic-3-GGUF/supertonic-3-orig.gguf", 454072836, ORIG),
        ListedFile("Supertonic-3-GGUF/supertonic-3-q8_0.gguf", 454072836, ORIG),
    ),
    None,
)


def test_the_entry_pins_its_folders_builds_in_its_own_order() -> None:
    """The written entry is one the app loads, typed by its family, with the
    reviewed builds only, most preferred first."""
    written = entry_for(ENTRY, SNAPSHOT, pinned_builds(ENTRY, SNAPSHOT), "supertonic")

    (model,) = LocalManifest.model_validate(
        {
            "schema_version": SCHEMA_VERSION,
            "refreshed_at": "2026-09-24",
            "models": [written],
        }
    ).models
    assert model.evidence.architecture == "supertonic"
    assert model.evidence.pipeline_tag == "text-to-speech"
    assert [b.quantization for b in model.builds] == ["F16", "orig"]
    f16 = model.builds[0].files[0]
    assert (f16.path, f16.revision) == ("Supertonic-3-GGUF/supertonic-3-f16.gguf", REV)
    assert model.audio is not None and model.audio.sample_rate == 44100


def test_a_build_the_entry_names_but_the_folder_lacks_is_refused() -> None:
    """Dropping it would quietly change the default a reviewer chose."""
    renamed = AudioEntry(**{**ENTRY.__dict__, "builds": ("BF16", "F16")})
    with pytest.raises(UnreadableBuildError):
        pinned_builds(renamed, SNAPSHOT)


# audio-cpp/audio.cpp-gguf at its 11 Oct 2026 commit, read on 14 Oct 2026.
ASR_REV = "f861648c0c1f4da9f18e9a0ce5e217b0679bb2f5"
NEMOTRON = AudioEntry(
    id="nemotron-3.5-asr-streaming-0.6b",
    name="Nemotron 3.5 ASR Streaming 0.6B",
    family="Nemotron",
    publisher="NVIDIA",
    description="Writes down speech in 26 languages.",
    license="openmdw-1.1",
    source_repo="nvidia/nemotron-3.5-asr-streaming-0.6b",
    repo="audio-cpp/audio.cpp-gguf",
    folder="Nemotron-3.5-ASR-Streaming-0.6B-GGUF",
    builds=("Q8_0",),
    transcription={
        "origin": "nvidia/nemotron-3.5-asr-streaming-0.6b model card",
        "sample_rate": 16000,
        "peak_mb": 1776,
        "window_s": 28,
        "detects_language": True,
        "languages": ["en", "ja"],
        "family_codes": {"en": "en-US", "ja": "ja-JP"},
        "request_options": {"keep_language_tags": True},
    },
)
ASR_SNAPSHOT = RepoAtRevision(
    NEMOTRON.repo,
    ASR_REV,
    "text-to-speech",
    (
        ListedFile(
            "Nemotron-3.5-ASR-Streaming-0.6B-GGUF/"
            "nemotron-3.5-asr-streaming-0.6b-f16.gguf",
            1277716512,
            "f02bb2fa14ad74b1deb2c63c36777fd81b546a696df096cd29ea3fe271b05c09",
        ),
        ListedFile(
            "Nemotron-3.5-ASR-Streaming-0.6B-GGUF/"
            "nemotron-3.5-asr-streaming-0.6b-q8_0.gguf",
            930625888,
            "c58b62c1bdd6c5d7b14b08126c5bd16c1289fee6e0d6ac0761dbd3aa6d714935",
        ),
    ),
    None,
)


def test_a_recognisers_entry_carries_its_languages_and_no_voices() -> None:
    """The same shared repo and folder rule as a voice model; the reviewed
    block is the recogniser's own."""
    written = entry_for(
        NEMOTRON,
        ASR_SNAPSHOT,
        pinned_builds(NEMOTRON, ASR_SNAPSHOT),
        "nemotron_asr",
        {
            "Nemotron-3.5-ASR-Streaming-0.6B-GGUF/"
            "nemotron-3.5-asr-streaming-0.6b-q8_0.gguf": "v0.8.2"
        },
    )

    assert "audio" not in written
    (model,) = LocalManifest.model_validate(
        {
            "schema_version": SCHEMA_VERSION,
            "refreshed_at": "2026-10-14",
            "models": [written],
        }
    ).models
    assert model.evidence.architecture == "nemotron_asr"
    assert model.transcription is not None
    assert model.transcription.family_codes == {"en": "en-US", "ja": "ja-JP"}
    (q8,) = model.builds
    assert q8.files[0].size_bytes == 930625888
    assert q8.validated.audio_cpp == "v0.8.2"
