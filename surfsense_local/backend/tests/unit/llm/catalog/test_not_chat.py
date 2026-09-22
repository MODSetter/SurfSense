"""The one list: what cannot hold a conversation, and what to say about it.

A denylist, not an allowlist. It names what we have seen and admits everything
else, which is the only way a list stays right as llama.cpp adds architectures.
The reverse ages badly: the hand written allowlist this replaces refused 43
architectures the runtime ran, including Gemma 4, while admitting `bert`, which
aborts the worker on the first message.

Two facts feed it and they share the table, because they answer the same
question and their names never collide:

    the GGUF header's architecture      what the file is built as
    the repo's pipeline tag             what the uploader says it is for

The second exists because the first can be honest and still mislead. Measured
across the 1000 most downloaded GGUF repos, an embedding model declares
`mistral3`, a voice model declares `qwen3` and a video encoder declares
`qwen35`. Refusing those architectures would refuse Mistral and Qwen.
"""

import pytest

from modules.llm.catalog.search import is_supported, refusal

pytestmark = pytest.mark.unit


def test_an_architecture_this_list_has_never_heard_of_is_admitted() -> None:
    """The denylist's whole contract, and the change from what came before.

    llama.cpp gains architectures faster than any list is updated. An unknown
    name is far more often a chat model released last week than something that
    cannot run, so the default is yes. The cost is a wasted download when we
    are wrong, and the chat error now says so plainly rather than telling the
    reader to try again shortly.
    """
    assert is_supported("glm5next")
    assert is_supported("something-invented-yesterday")


def test_an_embedding_architecture_is_refused() -> None:
    """It builds, loads, then aborts the worker on the first message.

    Measured against the pinned binary: a `nomic-bert` model reaches
    `GGML_ASSERT(n_outputs_max <= cparams.n_outputs_max)` and the router
    answers 500. Nothing downstream recovers, so the refusal belongs before
    the download.
    """
    assert not is_supported("nomic-bert")
    assert not is_supported("bert")
    assert not is_supported("gemma-embedding")


def test_a_chat_architecture_is_admitted() -> None:
    """The ordinary case, and the one the old allowlist got wrong: it refused
    Gemma 4 because nobody had retyped the list since llama.cpp added it."""
    assert is_supported("qwen3")
    assert is_supported("gemma4")


def test_the_gate_is_case_insensitive() -> None:
    """A header states its own architecture and publishers disagree on case."""
    assert is_supported("QWEN3")
    assert not is_supported("Nomic-Bert")


def test_a_model_wearing_a_chat_architecture_is_refused_by_its_tag() -> None:
    """The hole the header cannot see. `Nemotron-3-Embed-8B` declares
    `mistral3`, which is Mistral's architecture and cannot be refused."""
    assert is_supported("mistral3")
    assert not is_supported("mistral3", "sentence-similarity")


def test_a_vision_chat_model_is_not_refused_by_its_tag() -> None:
    """`image-text-to-text` is 28% of the catalog: every Qwen 3.5, every
    Gemma 4, every Qwen3 VL. Denying it would empty the search screen."""
    for tag in ("text-generation", "image-text-to-text", "any-to-any"):
        assert is_supported("qwen35", tag), tag


def test_an_untagged_repo_is_admitted() -> None:
    """Roughly four fifths of GGUF repos carry no tag. A missing tag is a
    missing answer, not a negative one."""
    assert is_supported("qwen3", None)
    assert is_supported("qwen3", "")


def test_a_file_for_different_software_says_that_rather_than_blaming_the_build(
) -> None:
    """Stable Diffusion and video GGUFs are packaged for other runtimes.

    Telling someone a newer SurfSense would run their FLUX checkpoint is a
    promise nothing will keep, and `pig` and `cow` are not architectures at
    all: they are literal placeholders gguf-connector writes into the header.
    """
    for name in ("flux", "wan", "sdxl", "pig", "cow"):
        reason = refusal(name)
        assert reason, name
        assert "newer" not in reason.lower(), name


def test_a_refusal_says_what_the_model_is_rather_than_naming_its_architecture(
) -> None:
    """The reader chose a model, not an architecture."""
    reason = refusal("nomic-bert")

    assert "nomic-bert" not in reason
    assert "search" in reason.lower()


def test_an_embedding_reads_the_same_whichever_fact_caught_it() -> None:
    """One table, one sentence. A user refused an embedding model should not
    get different words depending on which fact happened to catch it."""
    assert refusal("nomic-bert") == refusal("mistral3", "sentence-similarity")


def test_each_kind_of_refusal_reads_differently() -> None:
    """One sentence covering six situations is wrong in five of them."""
    reasons = {
        refusal(name)
        for name in ("nomic-bert", "qwen3tts", "paddleocr", "eagle3", "clip", "flux")
    }

    assert len(reasons) == 6


def test_a_supported_model_has_nothing_to_explain() -> None:
    """Asking why a runnable model was refused is a question with no answer."""
    assert refusal("qwen3") == ""
    assert refusal("qwen3", "text-generation") == ""


def test_refusal_copy_keeps_the_house_style() -> None:
    """No em dashes and no hyphens in anything a person reads."""
    from modules.llm.catalog.search.not_chat import NOT_CHAT

    for name in NOT_CHAT:
        reason = refusal(name)
        assert "—" not in reason
        assert "-" not in reason, reason


def test_the_tags_that_mean_chat_are_never_keys() -> None:
    """The most expensive mistake available in this file.

    `image-text-to-text` alone is 28% of architecture admitted repos. Adding
    any of these would turn away a whole family, silently and permanently.
    """
    from modules.llm.catalog.search.not_chat import NOT_CHAT

    for tag in (
        "text-generation",
        "image-text-to-text",
        "video-text-to-text",
        "audio-text-to-text",
        "any-to-any",
    ):
        assert tag not in NOT_CHAT, tag


def test_speech_to_text_models_are_refused() -> None:
    """The largest group that was installing and then failing.

    Measured over the 1000 most downloaded GGUF repos: 37 of the 75 that got
    through and could not load are transcription models. Their names are stable
    in a way a new chat architecture's is not, because llama.cpp is never going
    to turn Whisper into something that answers questions.
    """
    for name in ("whisper", "parakeet", "canary", "voxtral", "gigaam", "qwen3_asr"):
        assert not is_supported(name), name
    assert not is_supported("qwen2", "automatic-speech-recognition")


def test_transcription_reads_differently_from_reading_aloud() -> None:
    """Opposite directions. One sentence for both would be wrong for one."""
    assert refusal("whisper") != refusal("qwen3tts")


def test_models_that_label_things_are_refused() -> None:
    """Classifiers and detectors produce a label, not a conversation."""
    assert not is_supported("openai-privacy-filter")
    assert not is_supported("qwen3", "token-classification")
    assert not is_supported("qwen3", "object-detection")


def test_more_media_tools_are_refused() -> None:
    """Image and video tools that reached the top 1000 and installed."""
    for name in ("krea2", "seedvr", "birefnet-swinl", "minimax_h3"):
        assert not is_supported(name), name
    assert not is_supported("qwen3", "text-to-image")


def test_a_control_vector_is_not_a_model() -> None:
    """`creative-writing-control-vectors` ships steering vectors, not weights."""
    assert not is_supported("controlvector")


def test_a_new_chat_architecture_is_still_admitted() -> None:
    """The line this list must not cross.

    `glm5next` and `inkling` are chat models llama.cpp has not merged yet, and
    they carry `text-generation` like any other. Naming them here would refuse
    them for the few weeks they are unsupported and then keep refusing them
    forever, which is the drift this whole file is shaped to avoid.
    """
    assert is_supported("glm5next", "text-generation")
    assert is_supported("inkling", "image-text-to-text")
    assert is_supported("deepseek41", None)
