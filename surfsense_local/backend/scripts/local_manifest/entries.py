"""The hand-authored part of the local manifest: which models, in which order.

Position is preference within each type, most preferred first. The
recommendation walks this list from the top and stars the first model with a build that runs well on the
machine, so the order means "good at this app's job" (answering from the user's
documents with citations that resolve), not general capability. Everything else
in the written manifest is read from the files.
"""

from local_manifest.audiocpp.entry import AudioEntry
from local_manifest.entry import Entry
from local_manifest.sdcpp.entry import ImageEntry


def _qwen3(size: str, description: str) -> Entry:
    return Entry(
        id=f"qwen3-{size.lower()}",
        name=f"Qwen3 {size}",
        family="Qwen3",
        publisher="Qwen",
        description=description,
        license="apache-2.0",
        source_repo=f"Qwen/Qwen3-{size}",
        repo=f"unsloth/Qwen3-{size}-GGUF",
        aliases=(
            f"Qwen/Qwen3-{size}",
            f"Qwen/Qwen3-{size}-GGUF",
            f"bartowski/Qwen_Qwen3-{size}-GGUF",
        ),
    )


# Kokoro's packaged voices, `<language><gender>_<name>`. Its Japanese voices
# need a dictionary the release GGUF leaves out, and its `*_santa` voices are
# novelty voices, so neither is listed.
_KOKORO_LANGUAGES = {
    "a": "en-US",
    "b": "en-GB",
    "e": "es",
    "f": "fr",
    "h": "hi",
    "i": "it",
    "p": "pt-BR",
    "z": "zh",
}
# fmt: off
_KOKORO_VOICES = (
    "af_heart", "af_bella", "af_nicole", "af_nova", "af_sarah", "af_sky", "af_alloy",
    "af_aoede", "af_jessica", "af_kore", "af_river",
    "am_adam", "am_echo", "am_eric", "am_liam", "am_michael", "am_onyx", "am_puck",
    "am_fenrir",
    "bf_alice", "bf_emma", "bf_isabella", "bf_lily",
    "bm_daniel", "bm_fable", "bm_george", "bm_lewis",
    "ef_dora", "em_alex",
    "ff_siwis",
    "hf_alpha", "hf_beta", "hm_omega", "hm_psi",
    "if_sara", "im_nicola",
    "pf_dora", "pm_alex",
    "zf_xiaobei", "zf_xiaoni", "zf_xiaoxiao", "zf_xiaoyi",
    "zm_yunjian", "zm_yunxi", "zm_yunxia", "zm_yunyang",
)
# Supertonic 3's languages, from audio.cpp's model spec; every voice speaks all.
_SUPERTONIC_LANGUAGES = [
    "en", "ko", "ja", "ar", "bg", "cs", "da", "de", "el", "es", "et", "fi", "fr",
    "hi", "hr", "hu", "id", "it", "lt", "lv", "nl", "pl", "pt", "ro", "ru", "sk",
    "sl", "sv", "tr", "uk", "vi",
]
# fmt: on
# Measured while voicing through audio.cpp v0.8.2's server on an i5-1235U,
# 24 Sep 2026 (docs/proposals/local-audio-models.md, Measurements).
_MEASURED = "memory measured on audio.cpp v0.8.2, 24 Sep 2026"


ENTRIES: tuple[Entry, ...] = (
    _qwen3("32B", "The strongest answers here, for machines with 24 GB or more"),
    _qwen3("14B", "Careful answers from long documents, for 16 GB machines"),
    _qwen3("8B", "Balanced chat model for documents, fits most 12 GB machines"),
    _qwen3("4B", "Quick answers on 8 GB machines"),
    Entry(
        id="gemma-3-4b",
        name="Gemma 3 4B",
        family="Gemma 3",
        publisher="Google",
        description="Small chat model that also reads images, for 8 GB machines",
        license="gemma",
        # The vendor repo is gated and ships no GGUF; Unsloth's quantizations
        # are the ungated source of the builds.
        source_repo="google/gemma-3-4b-it",
        repo="unsloth/gemma-3-4b-it-GGUF",
        aliases=(
            "google/gemma-3-4b-it",
            "ggml-org/gemma-3-4b-it-GGUF",
            "bartowski/google_gemma-3-4b-it-GGUF",
        ),
    ),
    _qwen3("1.7B", "Light enough for older laptops"),
    _qwen3("0.6B", "The smallest that still answers, for any machine"),
    # Image models: one self-contained Q4_0 file each, the builds sd-server was
    # measured on here. Defaults are the publisher's, where the card states them.
    ImageEntry(
        id="stable-diffusion-1.5",
        name="Stable Diffusion 1.5",
        family="Stable Diffusion",
        publisher="Runway",
        description="Fastest, lowest memory. 512x512.",
        license="creativeml-openrail-m",
        source_repo="stable-diffusion-v1-5/stable-diffusion-v1-5",
        repo="kostakoff/stable-diffusion-v1-5-GGUF",
        aliases=("stable-diffusion-v1-5/stable-diffusion-v1-5",),
        image={
            "origin": "stable-diffusion-v1-5/stable-diffusion-v1-5 model card",
            "resolution": 512,
        },
    ),
    ImageEntry(
        id="sdxl-base-1.0",
        name="Stable Diffusion XL",
        family="Stable Diffusion",
        publisher="Stability AI",
        description="Higher detail at 1024x1024, and slower.",
        license="openrail++",
        source_repo="stabilityai/stable-diffusion-xl-base-1.0",
        repo="kostakoff/stable-diffusion-xl-base-1.0-GGUF",
        aliases=("stabilityai/stable-diffusion-xl-base-1.0",),
        # The card states no size; the SDXL report trains at 1024x1024.
        image={"origin": "SDXL report, arXiv:2307.01952", "resolution": 1024},
        # Its VAE decode alone can want about 10 GB of VRAM, so it decodes on
        # the CPU and the card holds only the diffusion model.
        run_args=("--backend", "vae=cpu"),
    ),
    # Audio models: podcast voices, from audio.cpp's own conversions. Kokoro
    # leads: the most voices, and the voice ids podcast briefs store today.
    AudioEntry(
        id="kokoro-82m",
        name="Kokoro 82M",
        family="Kokoro",
        publisher="hexgrad",
        description="46 natural voices in eight languages.",
        license="apache-2.0",
        source_repo="hexgrad/Kokoro-82M",
        repo="audio-cpp/audio.cpp-gguf",
        aliases=("hexgrad/Kokoro-82M",),
        folder="Kokoro-82M-GGUF",
        builds=("Q8_0", "BF16"),
        audio={
            "origin": f"hexgrad/Kokoro-82M model card; {_MEASURED}",
            "sample_rate": 24000,
            "peak_mb": 2347,
            "chunk_steps": [
                {"text_chunk_size": 120, "peak_mb": 1442},
                {"text_chunk_size": 60, "peak_mb": 956},
            ],
            "languages": sorted(set(_KOKORO_LANGUAGES.values())),
            "voices": [
                {
                    "id": voice,
                    "label": voice.split("_")[1].title(),
                    "language": _KOKORO_LANGUAGES[voice[0]],
                }
                for voice in _KOKORO_VOICES
            ],
        },
    ),
    AudioEntry(
        id="supertonic-3",
        name="Supertonic 3",
        family="Supertonic",
        publisher="Supertone",
        description="Ten voices, each in 31 languages, in the least memory.",
        # BigScience OpenRAIL-M: its use restrictions pass on to the user.
        license="openrail",
        source_repo="Supertone/supertonic-3",
        repo="audio-cpp/audio.cpp-gguf",
        aliases=("Supertone/supertonic-3",),
        folder="Supertonic-3-GGUF",
        # Its q8_0 file is the orig file under another name, same hash.
        builds=("F16", "orig"),
        audio={
            "origin": f"Supertone/supertonic-3 model card; {_MEASURED}",
            "sample_rate": 44100,
            "peak_mb": 486,
            "languages": _SUPERTONIC_LANGUAGES,
            "voices": [
                {"id": f"{gender}{n}", "label": f"{gender}{n}"}
                for gender in ("M", "F")
                for n in range(1, 6)
            ],
        },
    ),
    AudioEntry(
        id="kitten-tts-mini-0.8",
        name="KittenTTS Mini 0.8",
        family="KittenTTS",
        publisher="KittenML",
        description="Eight English voices.",
        license="apache-2.0",
        source_repo="KittenML/kitten-tts-mini-0.8",
        repo="audio-cpp/audio.cpp-gguf",
        aliases=("KittenML/kitten-tts-mini-0.8",),
        folder="KittenTTS-GGUF",
        builds=("orig",),
        audio={
            "origin": f"KittenML/kitten-tts-mini-0.8 model card; {_MEASURED}",
            "sample_rate": 24000,
            "peak_mb": 1863,
            "chunk_steps": [
                {"text_chunk_size": 240, "peak_mb": 1414},
                {"text_chunk_size": 120, "peak_mb": 1060},
                {"text_chunk_size": 60, "peak_mb": 852},
            ],
            "languages": ["en"],
            "voices": [
                {"id": name, "label": name, "language": "en"}
                for name in (
                    "Bella",
                    "Jasper",
                    "Luna",
                    "Bruno",
                    "Rosie",
                    "Hugo",
                    "Kiki",
                    "Leo",
                )
            ],
        },
    ),
)
