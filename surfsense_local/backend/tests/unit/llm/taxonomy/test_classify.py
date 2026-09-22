"""Fixtures are real models.dev entries; counts were measured over all 223 providers."""

import pytest

from modules.llm.taxonomy import ModelType, classify

pytestmark = pytest.mark.unit


def _entry(inputs: list[str], outputs: list[str], **rest: object) -> dict:
    return {
        "modalities": {"input": inputs, "output": outputs},
        "limit": {"context": 128000},
        **rest,
    }


def test_text_on_both_sides_is_the_chat_case() -> None:
    """The ordinary model, and the only shape a chat tab may offer."""
    assert classify("gpt-5", _entry(["text", "image"], ["text"])) == {
        ModelType.TEXT_GEN
    }


def test_an_image_model_given_an_image_both_generates_and_edits() -> None:
    """Reading image input as edit *instead of* generate empties the image tab
    at all twelve connectable providers, `gpt-image-1` included."""
    assert classify("gpt-image-1", _entry(["text", "image"], ["image"])) == {
        ModelType.IMAGE_GEN,
        ModelType.IMAGE_EDIT,
    }


def test_an_image_model_that_also_emits_text_is_not_a_chat_model() -> None:
    """The GPT image models declare text output, so modalities alone put them
    in the chat tab, where they answer with a picture. They report no context
    window, which a model you can converse with always has."""
    gpt_image = _entry(["text", "image"], ["text", "image"], limit={"context": 0})

    assert classify("gpt-image-1.5", gpt_image) == {
        ModelType.IMAGE_GEN,
        ModelType.IMAGE_EDIT,
    }


def test_an_image_model_that_takes_only_text_cannot_edit() -> None:
    """No image goes in, so there is nothing to edit."""
    assert classify("qwen-image-2.0", _entry(["text"], ["image"])) == {
        ModelType.IMAGE_GEN
    }


def test_transcription_is_not_a_chat_model() -> None:
    """Text out alone would admit all 33, and they ignore everything you type."""
    assert classify("openai/whisper-large-v3", _entry(["audio"], ["text"])) == set()


def test_a_model_that_cannot_be_given_text_is_offered_nowhere() -> None:
    """A speech translator emits audio but ignores a typed prompt. The same
    refusal covers the 33 transcription entries."""
    assert (
        classify("gemini-3.5-live-translate", _entry(["audio"], ["audio", "text"]))
        == set()
    )


def test_a_model_that_emits_two_media_carries_two_types() -> None:
    """165 entries are genuinely two things; collapsing that is what puts an
    image model in the chat list."""
    omni = _entry(["text", "image", "audio", "video"], ["text", "audio"])

    assert classify("qwen-omni-turbo", omni) == {
        ModelType.TEXT_GEN,
        ModelType.AUDIO_GEN,
    }


def test_video_out_is_video_generation() -> None:
    """Named because the type exists in the source, not because a tab wants it."""
    assert classify("happyhorse-1.1-t2v", _entry(["text"], ["video"])) == {
        ModelType.VIDEO_GEN
    }


def test_an_entry_that_declares_nothing_gets_no_type() -> None:
    """Skipped, not defaulted: every default lands it in a tab where it fails."""
    assert classify("mystery-model", {}) == set()


def test_an_embedding_model_is_not_a_chat_model() -> None:
    """Text on both sides and it cannot answer a word — the one type the
    declared modalities hide."""
    embedding = _entry(["text"], ["text"], limit={"context": 8191, "output": 1536})

    assert classify("text-embedding-3-small", embedding) == set()


def test_a_reranker_is_not_a_chat_model() -> None:
    """Its output limit is an ordinary 4096, so the name has to refuse it."""
    reranker = _entry(["text"], ["text"], limit={"context": 128000, "output": 4096})

    assert classify("Qwen/Qwen3-Reranker-4B", reranker) == set()


def test_a_small_output_limit_does_not_make_a_model_an_embedder() -> None:
    """Guards the rule we deliberately did not write: across 223 providers it
    refuses one model the names miss, and that one is a support chatbot."""
    support_bot = _entry(
        ["text"], ["text"], limit={"context": 8192, "output": 512}, cost={"output": 0}
    )

    assert classify("nano-gpt-help", support_bot) == {ModelType.TEXT_GEN}
