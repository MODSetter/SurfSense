"""The hand-authored part of the local manifest: which models, in which order.

Position is preference within each type, most preferred first. The
recommendation walks this list from the top and stars the first model with a build that runs well on the
machine, so the order means "good at this app's job" (answering from the user's
documents with citations that resolve), not general capability. Everything else
in the written manifest is read from the files.
"""

from local_manifest.audiocpp.entry import AudioEntry
from local_manifest.entry import Entry
from local_manifest.sdcpp.entry import Companion, ImageEntry, VideoEntry


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
# The text encoder FLUX.2 klein and Z-Image both run with: Comfy's copies of it
# are byte-identical in their two repos, and Z-Image's own shards match
# Qwen/Qwen3-4B, so one download serves both.
_QWEN3_4B = Companion("text_encoder", "unsloth/Qwen3-4B-GGUF", "Qwen3-4B-Q4_0.gguf")
_SD_CPP_DOCS = "sd.cpp docs at master-869-07a85c7"
# Every Wan model's text encoder, and the one download both curated ones share.
_UMT5 = Companion(
    "text_encoder", "city96/umt5-xxl-encoder-gguf", "umt5-xxl-encoder-Q4_K_M.gguf"
)

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
    # Image models. The newer families run with a text encoder and a VAE from
    # their own repos; SD 1 and XL carry theirs inside one Q4_0 file. Defaults
    # are sd.cpp's documented ones for the distilled builds, which the cards'
    # diffusers settings do not carry over to.
    ImageEntry(
        id="flux2-klein-4b",
        name="FLUX.2 klein 4B",
        family="FLUX.2",
        publisher="Black Forest Labs",
        description="Current image quality in four steps, in the least memory.",
        license="apache-2.0",
        source_repo="black-forest-labs/FLUX.2-klein-4B",
        repo="leejet/FLUX.2-klein-4B-GGUF",
        aliases=("black-forest-labs/FLUX.2-klein-4B",),
        builds=("Q4_0", "Q8_0"),
        companions=(
            _QWEN3_4B,
            Companion(
                "vae",
                "Comfy-Org/vae-text-encorder-for-flux-klein-4b",
                "split_files/vae/flux2-vae.safetensors",
                upstream_repo="black-forest-labs/FLUX.2-klein-4B",
            ),
        ),
        image={
            "origin": f"black-forest-labs/FLUX.2-klein-4B model card; {_SD_CPP_DOCS}, flux2.md",
            # One set of weights makes and edits: the card and sd.cpp's -r.
            "tasks": ["generate", "edit"],
            "resolution": 1024,
            "steps": 4,
            "cfg": 1.0,
            "sampler": "euler",
        },
    ),
    ImageEntry(
        id="z-image-turbo",
        name="Z-Image Turbo",
        family="Z-Image",
        publisher="Tongyi-MAI",
        description="Photographic detail in eight steps. Shares FLUX.2 klein's text encoder.",
        license="apache-2.0",
        source_repo="Tongyi-MAI/Z-Image-Turbo",
        repo="leejet/Z-Image-Turbo-GGUF",
        aliases=("Tongyi-MAI/Z-Image-Turbo",),
        builds=("Q4_0", "Q8_0"),
        companions=(
            _QWEN3_4B,
            Companion(
                "vae",
                "Comfy-Org/z_image_turbo",
                "split_files/vae/ae.safetensors",
                upstream_repo="black-forest-labs/FLUX.1-schnell",
            ),
        ),
        image={
            "origin": f"Tongyi-MAI/Z-Image-Turbo model card; {_SD_CPP_DOCS}, z_image.md",
            "resolution": 1024,
            "steps": 8,
            "cfg": 1.0,
        },
    ),
    ImageEntry(
        id="ernie-image-turbo",
        name="ERNIE-Image Turbo",
        family="ERNIE-Image",
        publisher="Baidu",
        description="Lettering and posters in eight steps.",
        license="apache-2.0",
        source_repo="baidu/ERNIE-Image-Turbo",
        repo="unsloth/ERNIE-Image-Turbo-GGUF",
        aliases=("baidu/ERNIE-Image-Turbo",),
        builds=("Q4_0", "Q8_0"),
        companions=(
            Companion(
                "text_encoder",
                "unsloth/Ministral-3-3B-Instruct-2512-GGUF",
                "Ministral-3-3B-Instruct-2512-Q4_0.gguf",
            ),
            Companion(
                "vae",
                "Comfy-Org/ERNIE-Image",
                "vae/flux2-vae.safetensors",
                upstream_repo="baidu/ERNIE-Image-Turbo",
            ),
        ),
        image={
            "origin": f"baidu/ERNIE-Image-Turbo model card; {_SD_CPP_DOCS}, ernie_image.md",
            "resolution": 1024,
            "steps": 8,
            "cfg": 1.0,
        },
    ),
    ImageEntry(
        id="longcat-image",
        name="LongCat-Image",
        family="LongCat",
        publisher="Meituan",
        description="Photographic detail and exact lettering, in English or Chinese. Slower: 50 steps.",
        license="apache-2.0",
        source_repo="meituan-longcat/LongCat-Image",
        # Two conversions, one per folder; sd.cpp's docs cite the comfy/ one.
        repo="vantagewithai/LongCat-Image-GGUF",
        folder="comfy",
        aliases=("meituan-longcat/LongCat-Image",),
        builds=("Q4_0", "Q8_0"),
        companions=(
            # sd.cpp's docs cite mradermacher's quantizations, which carry no
            # licence tag; unsloth's of the same model are Apache-2.0.
            Companion(
                "text_encoder",
                "unsloth/Qwen2.5-VL-7B-Instruct-GGUF",
                "Qwen2.5-VL-7B-Instruct-Q4_0.gguf",
            ),
            # The FLUX.1 VAE, the same file Z-Image Turbo runs with.
            Companion(
                "vae",
                "Comfy-Org/z_image_turbo",
                "split_files/vae/ae.safetensors",
                upstream_repo="black-forest-labs/FLUX.1-schnell",
            ),
        ),
        # Guidance, sampler and shift are sd.cpp's; the card's 50 steps, since
        # sd.cpp's example states none.
        image={
            "origin": f"meituan-longcat/LongCat-Image model card; {_SD_CPP_DOCS}, longcat_image.md",
            "resolution": 1024,
            "steps": 50,
            "cfg": 5.0,
            "sampler": "euler",
            "flow_shift": 3.0,
        },
    ),
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
    # Video models, which sd-server runs too. The lighter one leads until a
    # clip is measured on a laptop: the 5B leads if a 33-frame clip at 832x480
    # renders in under 10 minutes there. Settings are sd.cpp's for Wan.
    VideoEntry(
        id="wan2.1-t2v-1.3b",
        name="Wan2.1 T2V 1.3B",
        family="Wan",
        publisher="Wan-AI",
        description="Short clips from text, in the least memory.",
        license="apache-2.0",
        source_repo="Wan-AI/Wan2.1-T2V-1.3B",
        # A repo holding only this model; its GGUF is not one sd.cpp's docs
        # cite, which give only the fp16 safetensors.
        repo="samuelchristlie/Wan2.1-T2V-1.3B-GGUF",
        aliases=("Wan-AI/Wan2.1-T2V-1.3B",),
        builds=("Q8_0", "Q4_0"),
        companions=(
            _UMT5,
            Companion(
                "vae",
                "Comfy-Org/Wan_2.1_ComfyUI_repackaged",
                "split_files/vae/wan_2.1_vae.safetensors",
                upstream_repo="Wan-AI/Wan2.1-T2V-1.3B",
            ),
        ),
        video={
            "origin": f"Wan-AI/Wan2.1-T2V-1.3B model card; {_SD_CPP_DOCS}, wan.md",
            "tasks": ["text"],
            "width": 832,
            "height": 480,
            "frames": 33,
            "fps": 16,
            "cfg": 6.0,
            "sampler": "euler",
            "flow_shift": 3.0,
        },
    ),
    VideoEntry(
        id="wan2.2-ti2v-5b",
        name="Wan2.2 TI2V 5B",
        family="Wan",
        publisher="Wan-AI",
        description="Clips from text or an image, at 24 frames a second.",
        license="apache-2.0",
        source_repo="Wan-AI/Wan2.2-TI2V-5B",
        repo="QuantStack/Wan2.2-TI2V-5B-GGUF",
        aliases=("Wan-AI/Wan2.2-TI2V-5B",),
        builds=("Q4_0", "Q8_0"),
        companions=(
            _UMT5,
            # The one Wan model with its own VAE.
            Companion(
                "vae",
                "Comfy-Org/Wan_2.2_ComfyUI_Repackaged",
                "split_files/vae/wan2.2_vae.safetensors",
                upstream_repo="Wan-AI/Wan2.2-TI2V-5B",
            ),
        ),
        video={
            "origin": f"Wan-AI/Wan2.2-TI2V-5B model card; {_SD_CPP_DOCS}, wan.md",
            "tasks": ["text", "image"],
            "width": 832,
            "height": 480,
            "frames": 33,
            "fps": 24,
            "cfg": 6.0,
            "sampler": "euler",
            "flow_shift": 3.0,
        },
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
