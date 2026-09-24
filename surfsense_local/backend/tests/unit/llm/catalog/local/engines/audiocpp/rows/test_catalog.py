"""The manifest's audio models and the audio folder, as rows that say nothing
about this machine: an audio row states the memory it measured instead.
"""

import pytest

from modules.llm.catalog.local.engines.audiocpp.rows.catalog import audio_catalog
from modules.llm.catalog.local.installs import InstalledBuild
from modules.llm.catalog.local.manifest import load_local_manifest
from modules.llm.catalog.local.rows import LeadReason
from modules.llm.model_type import ModelType

pytestmark = pytest.mark.unit

MODELS = load_local_manifest().models


def rows(installs=None, files=(), selected=None):
    """The shipped manifest's audio rows against a folder."""
    return {
        r.id: r
        for r in audio_catalog(
            MODELS,
            installs or {},
            set(files),
            lambda b: f"id:{b.runtime_name}",
            selected=selected,
        )
    }


def test_every_curated_audio_model_is_a_runnable_unpriced_row() -> None:
    """Offered by audio.cpp, downloadable, never starred or badged, and led by
    the build the entry lists first."""
    result = rows()

    assert set(result) == {"kokoro-82m", "supertonic-3", "kitten-tts-mini-0.8"}
    kokoro = result["kokoro-82m"]
    assert kokoro.engine == "audiocpp"
    assert kokoro.classification.types == (ModelType.AUDIO_GEN,)
    assert kokoro.runnable and not kokoro.recommended
    assert [b.build.quantization for b in kokoro.builds] == ["Q8_0", "BF16"]
    assert all(
        b.fit is None and b.badge is None and b.can_install for b in kokoro.builds
    )
    assert kokoro.lead is not None
    assert (kokoro.lead.quantization, kokoro.lead.why) == ("Q8_0", LeadReason.DEFAULT)
    supertonic = result["supertonic-3"]
    assert supertonic.lead is not None and supertonic.lead.quantization == "F16"


def test_an_installed_build_is_its_own_models_only() -> None:
    """Every audio model shares one repo, and Supertonic and Kitten both have an
    `orig` build: only the recorded file says which model is installed."""
    record = InstalledBuild(
        model_id="supertonic-3-orig",
        repo="audio-cpp/audio.cpp-gguf",
        revision="0a104324546d2622985e3c676a4b5550cc772127",
        quantization="orig",
        weights=("supertonic-3-orig.gguf",),
    )

    result = rows(installs={record.model_id: record}, files={"supertonic-3-orig.gguf"})

    supertonic = result["supertonic-3"]
    assert [b.installed_as for b in supertonic.builds] == [None, "supertonic-3-orig"]
    assert supertonic.lead is not None and supertonic.lead.why is LeadReason.INSTALLED
    assert [b.installed_as for b in result["kitten-tts-mini-0.8"].builds] == [None]


def test_the_selected_audio_model_leads_as_in_use() -> None:
    """The row says which build the podcast's voices come from."""
    record = InstalledBuild(
        model_id="kokoro-82m-q8_0",
        repo="audio-cpp/audio.cpp-gguf",
        revision="0a104324546d2622985e3c676a4b5550cc772127",
        quantization="Q8_0",
        weights=("kokoro-82m-q8_0.gguf",),
    )

    kokoro = rows(
        installs={record.model_id: record},
        files={"kokoro-82m-q8_0.gguf"},
        selected="kokoro-82m-q8_0",
    )["kokoro-82m"]

    assert kokoro.lead is not None and kokoro.lead.why is LeadReason.IN_USE
