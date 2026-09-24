"""The curated local manifest: evidence, pinned file sets, reviewed defaults.

Source, not build output: a script writes it and a person reviews the diff, so
the schema is what catches a mistake before review does.
"""

import copy

import pytest
from pydantic import ValidationError

from modules.llm.catalog.local.build import FileRole
from modules.llm.catalog.local.manifest import (
    SCHEMA_VERSION,
    LocalManifest,
    load_local_manifest,
)

pytestmark = pytest.mark.unit

SHA = "a" * 64
REV = "3f2a" + "0" * 36


def file(role: str, path: str, size: int, **extra) -> dict:
    """One pinned file, as the refresh script writes it."""
    return {
        "role": role,
        "repo": "unsloth/gemma-3-4b-it-GGUF",
        "upstream_repo": None,
        "revision": REV,
        "path": path,
        "size_bytes": size,
        "sha256": SHA,
        **extra,
    }


PROJECTOR = file(
    "projector",
    "mmproj-F16.gguf",
    850,
    gguf={"general.type": "mmproj", "clip.has_vision_encoder": True},
)


def entry(**overrides) -> dict:
    """One well formed entry, before a test breaks a field."""
    base = {
        "id": "gemma-3-4b",
        "name": "Gemma 3 4B",
        "family": "Gemma 3",
        "publisher": "Google",
        "description": "Small chat model that reads images",
        "license": "gemma",
        "source_repo": "google/gemma-3-4b-it",
        "aliases": ["google/gemma-3-4b-it"],
        "evidence": {
            "architecture": "gemma3",
            "pipeline_tag": "image-text-to-text",
            "parameters_b": 3.9,
        },
        "context": 131072,
        "template": {"tools": False, "reasoning": False, "system_role": True},
        "sampling": None,
        "image": None,
        "shape": {
            "block_count": 34,
            "head_count_kv": 4,
            "key_length": 256,
            "value_length": 256,
            "n_vocab": 262144,
            "embedding_length": 2560,
            "feed_forward_length": 10240,
        },
        "builds": [
            {
                "quantization": "Q4_K_M",
                "files": [
                    file("weights", "gemma-3-4b-it-Q4_K_M.gguf", 2_490),
                    PROJECTOR,
                ],
                "run": {"args": []},
                "validated": {"llama_cpp": None},
            },
            {
                "quantization": "UD-Q4_K_XL",
                "files": [
                    file("weights", "gemma-3-4b-it-UD-Q4_K_XL.gguf", 2_540),
                    PROJECTOR,
                ],
                "run": {"args": []},
                "validated": {"llama_cpp": "b6500"},
            },
        ],
    }
    return {**base, **overrides}


def manifest(*models: dict) -> dict:
    """A whole manifest around the given entries."""
    return {
        "schema_version": SCHEMA_VERSION,
        "refreshed_at": "2026-09-23",
        "models": list(models) or [entry()],
    }


def test_a_well_formed_manifest_loads() -> None:
    """A well formed manifest loads."""
    parsed = LocalManifest.model_validate(manifest())

    (model,) = parsed.models
    assert model.id == "gemma-3-4b"
    assert model.model_shape.architecture == "gemma3"
    assert model.model_shape.context_length == 131072


def test_a_build_is_the_same_object_search_produces() -> None:
    """Curated and searched builds share one shape, so every reader of a build,
    the badge, fit, the downloader, never asks where it came from."""
    model = LocalManifest.model_validate(manifest()).models[0]

    build = model.as_builds()[1]
    assert build.quantization == "UD-Q4_K_XL"
    assert build.projector is not None and build.projector.role is FileRole.PROJECTOR
    assert build.projector.gguf["clip.has_vision_encoder"] is True
    assert build.footprint_bytes == 2_540 + 850
    assert build.weights.revision == REV


def test_every_file_is_pinned_and_verifiable() -> None:
    """Every file is pinned and verifiable."""
    for key, bad in (("revision", "main"), ("sha256", "abc"), ("size_bytes", 0)):
        broken = entry()
        broken["builds"][0]["files"][0][key] = bad
        with pytest.raises(ValidationError):
            LocalManifest.model_validate(manifest(broken))


def test_a_build_needs_weights_and_at_most_one_projector() -> None:
    """A build needs weights and at most one projector."""
    no_weights = entry()
    no_weights["builds"][0]["files"] = [PROJECTOR]
    two_projectors = entry()
    two_projectors["builds"][0]["files"].append(copy.deepcopy(PROJECTOR))

    for broken in (no_weights, two_projectors):
        with pytest.raises(ValidationError):
            LocalManifest.model_validate(manifest(broken))


def test_ids_and_quantizations_do_not_repeat() -> None:
    """Ids and quantizations do not repeat."""
    with pytest.raises(ValidationError):
        LocalManifest.model_validate(manifest(entry(), entry()))

    doubled = entry()
    doubled["builds"][1]["quantization"] = "Q4_K_M"
    with pytest.raises(ValidationError):
        LocalManifest.model_validate(manifest(doubled))


def test_a_label_carries_no_score() -> None:
    """Preference is list position and nothing else."""
    for field in ("score", "quality", "rank"):
        with pytest.raises(ValidationError):
            LocalManifest.model_validate(manifest(entry(**{field: 1})))


def test_the_shipped_manifest_loads() -> None:
    """The shipped manifest loads."""
    shipped = load_local_manifest()

    assert shipped.schema_version == SCHEMA_VERSION
    assert shipped.models
    for model in shipped.models:
        assert model.builds


def image_entry(**overrides) -> dict:
    """SD 1.5 as sd.cpp runs it: one self-contained file, no chat fields."""
    base = {
        "id": "stable-diffusion-1.5",
        "name": "Stable Diffusion 1.5",
        "family": "Stable Diffusion",
        "publisher": "Runway",
        "description": "Fastest, lowest memory. 512x512.",
        "license": "creativeml-openrail-m",
        "source_repo": "stable-diffusion-v1-5/stable-diffusion-v1-5",
        "evidence": {"architecture": "sd1", "pipeline_tag": "text-to-image"},
        "image": {
            "origin": "stable-diffusion-v1-5/stable-diffusion-v1-5 model card",
            "resolution": 512,
            "steps": 20,
            "cfg": 7.0,
            "sampler": "euler_a",
        },
        "builds": [
            {
                "quantization": "Q4_0",
                "files": [
                    {
                        **file("weights", "v1-5-pruned_Q4_0.gguf", 3_051_366_272),
                        "repo": "kostakoff/stable-diffusion-v1-5-GGUF",
                    }
                ],
                "validated": {"sd_cpp": "master-869-07a85c7"},
            }
        ],
    }
    return {**base, **overrides}


def audio_entry(**overrides) -> dict:
    """Kokoro as audio.cpp runs it: one file, its voices and its measured memory."""
    base = {
        "id": "kokoro-82m",
        "name": "Kokoro 82M",
        "family": "Kokoro",
        "publisher": "hexgrad",
        "description": "Natural voices in eight languages.",
        "license": "apache-2.0",
        "source_repo": "hexgrad/Kokoro-82M",
        "evidence": {"architecture": "kokoro_tts", "pipeline_tag": "text-to-speech"},
        "audio": {
            "origin": "hexgrad/Kokoro-82M model card",
            "sample_rate": 24000,
            "peak_mb": 1421,
            "chunk_steps": [
                {"text_chunk_size": 120, "peak_mb": 1215},
                {"text_chunk_size": 60, "peak_mb": 871},
            ],
            "languages": ["en-US", "en-GB"],
            "voices": [
                {"id": "af_heart", "label": "Heart", "language": "en-US"},
                {"id": "bm_fable", "label": "Fable", "language": "en-GB"},
            ],
        },
        "builds": [
            {
                "quantization": "Q8_0",
                "files": [
                    {
                        **file(
                            "weights",
                            "Kokoro-82M-GGUF/kokoro-82m-q8_0.gguf",
                            189_523_648,
                        ),
                        "repo": "audio-cpp/audio.cpp-gguf",
                    }
                ],
                "validated": {"audio_cpp": "v0.8.2"},
            }
        ],
    }
    return {**base, **overrides}


def test_an_image_model_needs_no_chat_fields() -> None:
    """No context window, template, sampling or fit shape: sd.cpp reads none."""
    (model,) = LocalManifest.model_validate(manifest(image_entry())).models

    assert model.context is None
    assert model.model_shape is None
    assert model.image is not None and model.image.resolution == 512
    assert model.builds[0].validated.sd_cpp == "master-869-07a85c7"


@pytest.mark.parametrize(
    "broken",
    [
        pytest.param(entry(context=None), id="a chat model without its window"),
        pytest.param(
            entry(image=image_entry()["image"]), id="a chat model with image defaults"
        ),
        pytest.param(image_entry(image=None), id="an image model without its defaults"),
        pytest.param(
            image_entry(shape=entry()["shape"]), id="an image model with a fit shape"
        ),
        pytest.param(image_entry(context=4096), id="an image model with a window"),
        pytest.param(audio_entry(audio=None), id="an audio model without its voices"),
        pytest.param(
            entry(audio=audio_entry()["audio"]), id="a chat model with voices"
        ),
        pytest.param(
            audio_entry(image=image_entry()["image"]),
            id="an audio model with image defaults",
        ),
        pytest.param(
            audio_entry(shape=entry()["shape"]), id="an audio model with a fit shape"
        ),
    ],
)
def test_a_model_carries_its_own_engines_fields_and_no_others(broken: dict) -> None:
    """The evidence says which engine runs a model, and that engine says which
    committed fields it reads. A field no engine reads would be reviewed and
    trusted while doing nothing."""
    with pytest.raises(ValidationError):
        LocalManifest.model_validate(manifest(broken))


def test_an_audio_model_carries_its_voices_and_memory() -> None:
    """The server lists neither, so the manifest commits both."""
    (model,) = LocalManifest.model_validate(manifest(audio_entry())).models

    assert model.audio is not None
    assert [v.id for v in model.audio.voices] == ["af_heart", "bm_fable"]
    assert model.audio.peak_mb == 1421
    assert [s.text_chunk_size for s in model.audio.chunk_steps] == [120, 60]
    assert model.builds[0].validated.audio_cpp == "v0.8.2"


def _voices(*voices: dict) -> dict:
    return {**audio_entry()["audio"], "voices": list(voices)}


HEART = {"id": "af_heart", "label": "Heart", "language": "en-US"}


@pytest.mark.parametrize(
    "audio",
    [
        pytest.param(_voices(HEART), id="one voice, and a podcast has two speakers"),
        pytest.param(_voices(HEART, HEART), id="a voice listed twice"),
        pytest.param(
            _voices(HEART, {"id": "ff_siwis", "label": "Siwis", "language": "fr"}),
            id="a voice in a language the model does not list",
        ),
    ],
)
def test_an_audio_models_voices_hold_together(audio: dict) -> None:
    """Checked here, before review: every voice is one a podcast speaker can use."""
    with pytest.raises(ValidationError):
        LocalManifest.model_validate(manifest(audio_entry(audio=audio)))
