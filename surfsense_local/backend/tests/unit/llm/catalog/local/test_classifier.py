"""What a local model is, from its architecture and its repo's tag.

A denylist in shape: anything unnamed is a chat model, because llama.cpp gains
architectures faster than any list is updated. The tag only refuses or refines,
never admits, because a header can be honest and still mislead: an embedding
model declares `mistral3`, a voice model `qwen3`.
"""

import pytest

from modules.llm.catalog.local.classifier import GROUPS, NotRunnableCode, classify
from modules.llm.catalog.local.install.codes import InstallCode
from modules.llm.model_type import ModelType

pytestmark = pytest.mark.unit

TEXT = (ModelType.TEXT_GEN,)


def test_an_architecture_nobody_has_named_is_a_chat_model() -> None:
    """An architecture nobody has named is a chat model."""
    for name in ("glm5next", "something-invented-yesterday", "qwen3", "gemma4"):
        assert classify(name).types == TEXT, name


def test_a_chat_model_has_nothing_to_explain() -> None:
    """A chat model has nothing to explain."""
    assert classify("qwen3", "text-generation").reason == ""


def test_things_that_produce_no_type_are_known_and_typeless() -> None:
    """Things that produce no type are known and typeless."""
    for name in (
        "whisper",
        "paddleocr",
        "eagle3",
        "clip",
        "controlvector",
    ):
        found = classify(name)
        assert found.types == (), name
        assert found.known, name
        assert found.reason, name


def test_an_embedder_is_an_embedding_model() -> None:
    """A catalog type, so an engine can run it; never a slot, which selection enforces."""
    for name in ("nomic-bert", "Nomic-Bert", "feature-extraction"):
        assert classify(name).types == (ModelType.EMBEDDING,), name
    # The tag refines a chat architecture: llm2vec-style embedders declare one.
    assert classify("mistral3", "sentence-similarity").types == (ModelType.EMBEDDING,)


def test_diffusion_video_and_speech_get_their_own_type() -> None:
    """They were refused because the old catalog was text only. They are
    classified, listed, and not runnable by the local chat runtime."""
    assert classify("flux").types == (ModelType.IMAGE_GEN,)
    assert classify("sdxl").types == (ModelType.IMAGE_GEN,)
    assert classify("wan").types == (ModelType.VIDEO_GEN,)
    assert classify("qwen3tts").types == (ModelType.AUDIO_GEN,)
    assert classify("qwen3", "image-to-image").types == (ModelType.IMAGE_EDIT,)


def test_the_tag_refines_a_chat_architecture() -> None:
    """The tag refines a chat architecture."""
    assert classify("qwen3", "text-to-speech").types == (ModelType.AUDIO_GEN,)
    assert classify("qwen2", "automatic-speech-recognition").types == ()


def test_the_tags_that_mean_chat_never_refuse() -> None:
    """`image-text-to-text` is 28% of admitted repos: every Gemma 4 and Qwen3 VL."""
    for tag in (
        "text-generation",
        "image-text-to-text",
        "video-text-to-text",
        "audio-text-to-text",
        "any-to-any",
    ):
        assert tag not in GROUPS, tag
        assert classify("qwen35", tag).types == TEXT, tag


def test_case_does_not_matter() -> None:
    """Case does not matter."""
    assert classify("QWEN3").types == TEXT


def test_an_unreadable_header_fails_open_to_chat_marked_approximate() -> None:
    """Refusing on a failed read hides models the user can run."""
    found = classify("", readable=False)

    assert found.types == TEXT
    assert found.approximate


def test_one_kind_reads_the_same_whichever_fact_caught_it() -> None:
    """One kind reads the same whichever fact caught it."""
    assert (
        classify("nomic-bert").reason
        == classify("mistral3", "sentence-similarity").reason
    )


def test_each_kind_reads_differently() -> None:
    """Each kind reads differently."""
    reasons = {
        classify(name).reason
        for name in (
            "nomic-bert",
            "qwen3tts",
            "whisper",
            "paddleocr",
            "eagle3",
            "clip",
            "flux",
            "wan",
        )
    }
    assert len(reasons) == 8


def test_the_copy_keeps_the_house_style() -> None:
    """No em dashes and no hyphens in anything a person reads."""
    for name in GROUPS:
        reason = classify(name).reason
        assert "—" not in reason and "-" not in reason, reason


def test_audio_cpps_voice_families_read_text_aloud() -> None:
    """A curated audio.cpp entry's architecture is its family, which is what
    audio.cpp dispatches on."""
    for family in ("kokoro_tts", "supertonic", "kitten_tts"):
        assert classify(family).types == (ModelType.AUDIO_GEN,), family


def test_a_bare_audio_cpp_file_is_not_offered_from_search() -> None:
    """Every audio.cpp file declares `audiocpp`, speech recognisers included, so
    the architecture alone says neither direction, even beside a TTS tag."""
    classification = classify("audiocpp", "text-to-speech")
    assert classification.types == ()
    assert classification.reason == (
        "This model runs on audio.cpp. SurfSense runs only the voices in its list."
    )


def test_every_refusal_has_a_code_and_a_chat_model_has_none() -> None:
    """The interface words a refusal by its code; a model that runs has neither."""
    for name in GROUPS:
        found = classify(name)
        assert found.code in set(NotRunnableCode), name
        assert found.code is not NotRunnableCode.UNSUPPORTED, name
    assert classify("qwen3", "text-generation").code is None
    assert classify("qwen3", readable=False).code is None


def test_a_code_names_one_sentence_and_a_sentence_one_code() -> None:
    """A translation is keyed by the code, so two sentences under one code
    would show the wrong one in every language but English."""
    pairs = {(group.code, group.reason) for group in GROUPS.values()}

    assert len({code for code, _ in pairs}) == len(pairs)
    assert len({reason for _, reason in pairs}) == len(pairs)
    # Every code but the fallback, which no group uses.
    assert {code for code, _ in pairs} == set(NotRunnableCode) - {
        NotRunnableCode.UNSUPPORTED
    }


def test_a_refusal_code_is_never_an_install_code() -> None:
    """An install refused for what the file is carries the classifier's code
    where its own would go, so the interface must be able to tell them apart."""
    assert not {c.value for c in NotRunnableCode} & {c.value for c in InstallCode}
