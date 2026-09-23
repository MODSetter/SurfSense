"""What a local model is: its architecture and its repo's tag in, a type out.

**A denylist in shape.** It names what is not a chat model and calls everything
else `TEXT_GEN`. llama.cpp gains architectures every few weeks, so an unnamed
architecture is far more often a chat model released last week than anything
else. The allowlist this replaced refused 43 architectures the runtime ran.

**Two facts, one table.** The header states an architecture, the repo states a
pipeline tag, and their names never collide. The tag exists because a header
can be honest and still mislead: measured, an embedding model declares
`mistral3`, a voice model `qwen3`, a video encoder `qwen35`. The tag only ever
refuses or refines, never admits: the tags that mean chat (`text-generation`,
`image-text-to-text`, `video-text-to-text`, `audio-text-to-text`, `any-to-any`)
are not keys and must never be.

Grouped by what the model is, so adding an entry answers one question. Each
group keeps its own sentence, which is why a type alone is not enough.
"""

from dataclasses import dataclass

from modules.llm.model_type import ModelType

_EMBEDDING = (
    "bert",
    "nomic-bert",
    "nomic-bert-moe",
    "neo-bert",
    "jina-bert-v2",
    "jina-bert-v3",
    "modern-bert",
    "eurobert",
    "llama-embed",
    "gemma-embedding",
    "t5",
    "t5encoder",
    "sentence-similarity",
    "text-ranking",
    "feature-extraction",
    "fill-mask",
    # llm2vec wraps a chat model as an encoder, so the architecture reads as chat
    "kimodo-llm2vec",
)
_SPEECH_OUT = (
    "qwen3tts",
    "qwen3-tts",
    "pockettts",
    "talkie",
    "wavtokenizer-dec",
    "higgs_tts",
    "sanotts",
    "echo_tts",
    "fish-speech",
    "omnivoice-lm",
    "piper",
    "vibevoice-tokenizer",
    "acestep-lm",
    "acestep-vae",
    "mm3-cond",
    "text-to-speech",
    "text-to-audio",
)
_SPEECH_IN = (
    "whisper",
    "parakeet",
    "canary",
    "canary_qwen",
    "asr",
    "qwen3_asr",
    "voxtral",
    "voxtral_realtime",
    "gigaam",
    "cohere_asr",
    "granite_speech",
    "granite_speech_nar",
    "sortformer",
    "funasr_nano",
    "sensevoice-small",
    "audiocpp",
    "ced",
    "automatic-speech-recognition",
    "audio-classification",
)
_LABELLERS = (
    "openai-privacy-filter",
    "locateanything",
    "birefnet-swinl",
    "token-classification",
    "object-detection",
    "image-segmentation",
    "image-to-3d",
)
_OCR = ("paddleocr", "deepseek2-ocr")
_DRAFTERS = ("eagle3", "dflash")
_PROJECTORS = ("clip",)
_NOT_WEIGHTS = ("controlvector",)
_IMAGE = (
    "flux",
    "flux2",
    "qwen_image",
    "z_image",
    "lumina2",
    "sd1",
    "sd3",
    "sdxl",
    "aura",
    "hidream",
    "krea2",
    # not architectures at all: the placeholders gguf-connector writes into
    # general.architecture for its diffusion GGUFs
    "pig",
    "cow",
    "text-to-image",
)
_IMAGE_EDIT = ("image-to-image",)
_VIDEO = (
    "ltxv",
    "wan",
    "cosmos",
    "hyvid",
    "seedvr",
    "minimax_h3",
    "text-to-video",
    "image-to-video",
    "video-to-video",
)


@dataclass(frozen=True)
class Group:
    types: tuple[ModelType, ...]
    reason: str


_NONE = ()
GROUPS: dict[str, Group] = {
    **dict.fromkeys(
        _EMBEDDING,
        Group(
            _NONE,
            (
                "This model turns text into numbers for search. It cannot answer "
                "questions, and SurfSense already has its own."
            ),
        ),
    ),
    **dict.fromkeys(
        _SPEECH_OUT,
        Group(
            (ModelType.AUDIO_GEN,),
            ("This model reads text aloud. SurfSense cannot run speech models yet."),
        ),
    ),
    **dict.fromkeys(
        _SPEECH_IN,
        Group(
            _NONE,
            (
                "This model writes down what it hears in audio. It cannot answer questions."
            ),
        ),
    ),
    **dict.fromkeys(
        _LABELLERS,
        Group(
            _NONE, ("This model puts labels on things. It cannot hold a conversation.")
        ),
    ),
    **dict.fromkeys(
        _OCR,
        Group(
            _NONE,
            (
                "This model reads text out of images in one pass. It cannot hold a conversation."
            ),
        ),
    ),
    **dict.fromkeys(
        _DRAFTERS,
        Group(
            _NONE,
            ("This file makes another model faster. It cannot answer on its own."),
        ),
    ),
    **dict.fromkeys(
        _PROJECTORS,
        Group(
            _NONE,
            (
                "This is the vision half of another model. Install the model it belongs to instead."
            ),
        ),
    ),
    **dict.fromkeys(
        _NOT_WEIGHTS,
        Group(_NONE, ("This file steers another model. It is not a model on its own.")),
    ),
    **dict.fromkeys(
        _IMAGE,
        Group(
            (ModelType.IMAGE_GEN,),
            ("This model makes pictures. SurfSense cannot run it from search yet."),
        ),
    ),
    **dict.fromkeys(
        _IMAGE_EDIT,
        Group(
            (ModelType.IMAGE_EDIT,),
            ("This model edits pictures. SurfSense cannot run picture editing yet."),
        ),
    ),
    **dict.fromkeys(
        _VIDEO,
        Group(
            (ModelType.VIDEO_GEN,),
            ("This model makes video. SurfSense cannot run video models yet."),
        ),
    ),
}

_TEXT = (ModelType.TEXT_GEN,)


@dataclass(frozen=True)
class Classification:
    """What a model is for. `reason` says why the local chat runtime cannot run
    it, and is empty for a chat model."""

    types: tuple[ModelType, ...]
    known: bool = True
    approximate: bool = False
    reason: str = ""


def classify(
    architecture: str, pipeline_tag: str | None = None, *, readable: bool = True
) -> Classification:
    """The architecture first, because it describes the file; then the tag.

    An unreadable header fails open to `TEXT_GEN`, marked approximate: refusing
    on a failed read hides models the user can run, and the runtime refuses with
    its own error if this was wrong.
    """
    if not readable:
        return Classification(_TEXT, approximate=True)
    for name in (architecture, pipeline_tag):
        if name and (group := GROUPS.get(name.lower())):
            return Classification(group.types, reason=group.reason)
    return Classification(_TEXT)
