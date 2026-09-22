"""What cannot hold a conversation here, and the sentence a person reads.

**A denylist.** It names what we have seen and admits everything else. That
direction is chosen for how it ages, not for its size: llama.cpp gains
architectures every few weeks, so an unknown name is far more often a chat
model released last week than something that cannot run. The reverse ages
badly, and did. The hand written allowlist this replaces refused 43
architectures the runtime supported, including Gemma 4 and Qwen 3.5, while
admitting `bert` and `t5encoder`, which abort the worker on the first message.
Three of its entries were misspelled, so they had never matched anything and
nobody could tell.

The cost of the denylist direction is a model that gets installed and then
cannot load. That is accepted: the curated models are the default path, search
is opt in, and `ChatErrorKind.MODEL_CANNOT_RUN` now says plainly that the file
cannot run rather than telling the reader to try again shortly.

**Two facts, one table.** A GGUF header states an architecture and a repo
states a pipeline tag. They share this dict because they answer the same
question and their names never collide.

The tag exists because the header can be honest and still mislead. Measured
across the most downloaded GGUF repos, an embedding model declares `mistral3`,
a voice model declares `qwen3`, a reranker declares `qwen3` and a video encoder
declares `qwen35`. Refusing those architectures would refuse Mistral and Qwen,
so only the tag can catch them. Tags here are the ones a real repo has actually
carried; a tag is added when the audit finds one, never on speculation.

The tags that mean chat are not here and must never be: `text-generation`,
`image-text-to-text`, `video-text-to-text`, `audio-text-to-text` and
`any-to-any`. `image-text-to-text` alone is 28% of admitted repos.

Grouped by what the model **is**, never by which fact named it, so adding an
entry means answering one question: what kind of model is this.
"""

__all__ = ["NOT_CHAT", "is_supported", "refusal"]

_EMBEDDING_COPY = (
    "This model turns text into numbers for search. It cannot answer "
    "questions, and SurfSense already has its own."
)
_SPEECH_OUT_COPY = "This model reads text aloud. It cannot answer questions."
_OCR_COPY = (
    "This model reads text out of images in one pass. It cannot hold a "
    "conversation."
)
_DRAFTER_COPY = "This file makes another model faster. It cannot answer on its own."
_PROJECTOR_COPY = (
    "This is the vision half of another model. Install the model it belongs "
    "to instead."
)
_SPEECH_IN_COPY = (
    "This model writes down what it hears in audio. It cannot answer questions."
)
_LABELLER_COPY = (
    "This model puts labels on things. It cannot hold a conversation."
)
_OTHER_RUNTIME_COPY = (
    "This file makes pictures or video and needs different software. "
    "SurfSense runs models that chat."
)

_EMBEDDING = (
    # architectures
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
    # tags, measured on real repos
    "sentence-similarity",
    "text-ranking",
    "feature-extraction",
    "fill-mask",
    # llm2vec wraps a chat model as an encoder, so the architecture reads as chat
    "kimodo-llm2vec",
)
# Measured: a `nomic-bert` model reaches
# `GGML_ASSERT(n_outputs_max <= cparams.n_outputs_max)` and the router answers
# 500. bge-small already fills the embedding role and is not chosen here. The
# two tags catch `Nemotron-3-Embed` and `jina-embeddings-v5`, which declare
# `mistral3` and `qwen3`, and `Qwen3-Reranker`, which declares `qwen3`.

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
# Audio out. Kokoro owns that role. The tag catches `VieNeu-TTS`, which
# declares `qwen3`.

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
# The largest group that installed and then failed: 37 of the 75 measured over
# the top 1000 repos. Unlike a new chat architecture, these names are stable,
# because llama.cpp is never going to make Whisper answer questions. Named by
# architecture as well as by tag, the way Unsloth does it, since the
# architecture comes from the file while the tag comes from the uploader.

_LABELLERS = (
    "openai-privacy-filter",
    "locateanything",
    "birefnet-swinl",
    "token-classification",
    "object-detection",
    "image-segmentation",
)
# A label or a bounding box is not a conversation.

_OCR = ("paddleocr", "deepseek2-ocr")
# Image to text in one shot, not a conversation about a document.

_DRAFTERS = ("eagle3", "dflash")
# Speculative draft heads. They accelerate another model and answer nothing on
# their own; `list_builds` already drops files named for them, which this
# backstops for a repo that names them something else.

_PROJECTORS = ("clip",)
# Half of a vision model. The weights it pairs with are the installable thing.

_OTHER_RUNTIME = (
    # diffusion and video GGUFs, packaged for stable-diffusion.cpp or ComfyUI
    "flux",
    "qwen_image",
    "lumina2",
    "ltxv",
    "wan",
    "cosmos",
    "hyvid",
    "sd1",
    "sd3",
    "sdxl",
    "aura",
    "hidream",
    # not architectures at all: the literal placeholders gguf-connector writes
    # into general.architecture for its diffusion GGUFs
    "pig",
    "cow",
    "krea2",
    "seedvr",
    "minimax_h3",
    # a steering vector file, not weights
    "controlvector",
    # tags, measured on real repos
    "text-to-video",
    "image-to-video",
    "text-to-image",
    "image-to-image",
    "video-to-video",
    "image-to-3d",
)
# llama.cpp has no builder for any of these and never will, so the honest
# sentence names other software rather than a newer version of this one. The
# two tags catch `MiniMax-H3` and `Sulphur-2`, which declare `qwen3vl` and
# `qwen35`.

# The one judgement in this module, and the only thing here a person edits.
# Each group keeps its own sentence, because one line covering six situations
# would be wrong in seven of them.
NOT_CHAT: dict[str, str] = {
    **dict.fromkeys(_EMBEDDING, _EMBEDDING_COPY),
    **dict.fromkeys(_SPEECH_OUT, _SPEECH_OUT_COPY),
    **dict.fromkeys(_SPEECH_IN, _SPEECH_IN_COPY),
    **dict.fromkeys(_LABELLERS, _LABELLER_COPY),
    **dict.fromkeys(_OCR, _OCR_COPY),
    **dict.fromkeys(_DRAFTERS, _DRAFTER_COPY),
    **dict.fromkeys(_PROJECTORS, _PROJECTOR_COPY),
    **dict.fromkeys(_OTHER_RUNTIME, _OTHER_RUNTIME_COPY),
}


def refusal(architecture: str, pipeline_tag: str | None = None) -> str:
    """Why this model cannot chat here, or empty when it can.

    Both facts are looked up in the same table, the architecture first because
    it describes the file while the tag describes the repo around it. Empty for
    anything that installs fine, so a caller cannot attach an explanation to a
    row that has nothing to explain.
    """
    for name in (architecture, pipeline_tag):
        if name and (found := NOT_CHAT.get(name.lower())):
            return found
    return ""


def is_supported(architecture: str, pipeline_tag: str | None = None) -> bool:
    """Whether a model described this way is worth downloading."""
    return not refusal(architecture, pipeline_tag)
