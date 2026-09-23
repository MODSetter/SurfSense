"""What a local build can do, read from GGUF keys under their own names."""

import pytest

from modules.llm.catalog.local.engines.llamacpp.support import (
    projector_fits_model,
    projector_reads_images,
    template_support,
)

pytestmark = pytest.mark.unit

VISION_PROJECTOR = {
    "general.type": "mmproj",
    "general.architecture": "clip",
    "clip.has_vision_encoder": True,
    "clip.vision.projection_dim": 2560,
}
GEMMA = {"general.architecture": "gemma3", "gemma3.embedding_length": 2560}


def test_a_projector_with_a_vision_encoder_reads_images() -> None:
    """A projector with a vision encoder reads images."""
    assert projector_reads_images(VISION_PROJECTOR)


def test_an_audio_only_projector_does_not() -> None:
    """An audio only projector does not."""
    audio = {"general.type": "mmproj", "clip.has_audio_encoder": True}

    assert not projector_reads_images(audio)


def test_a_model_file_is_not_a_projector() -> None:
    """A model file is not a projector."""
    assert not projector_reads_images(GEMMA)


def test_an_older_projector_is_known_by_its_clip_architecture() -> None:
    """An older projector is known by its clip architecture."""
    older = {"general.architecture": "clip", "clip.has_vision_encoder": True}

    assert projector_reads_images(older)


def test_a_projector_belongs_to_a_model_of_its_width() -> None:
    """A projector belongs to a model of its width."""
    assert projector_fits_model(VISION_PROJECTOR, GEMMA)


def test_a_projector_for_another_model_does_not() -> None:
    """A projector for another model does not."""
    wider = {"general.architecture": "gemma3", "gemma3.embedding_length": 3840}

    assert not projector_fits_model(VISION_PROJECTOR, wider)


def test_a_width_nobody_wrote_cannot_be_held_against_the_pair() -> None:
    """A width nobody wrote cannot be held against the pair."""
    silent = {
        k: v for k, v in VISION_PROJECTOR.items() if k != "clip.vision.projection_dim"
    }

    assert projector_fits_model(silent, GEMMA)


def test_the_template_says_what_a_request_may_carry() -> None:
    """The template says what a request may carry."""
    qwen3 = (
        "{%- if tools %}<tools>{% endif %}{%- if message.role == 'system' %}"
        "{%- if enable_thinking is defined and enable_thinking is false %}<think>\n\n</think>"
    )

    assert template_support(qwen3) == (True, True)
    assert template_support("{{ messages[0]['content'] }}") == (False, False)


def test_no_template_is_silence_not_no() -> None:
    """No template is silence not no."""
    assert template_support(None) == (None, None)
