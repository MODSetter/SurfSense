"""The hand-authored part of the local manifest: which models, in which order.

Position is preference within each type, most preferred first. The
recommendation walks this list from the top and stars the first model with a build that runs well on the
machine, so the order means "good at this app's job" (answering from the user's
documents with citations that resolve), not general capability. Everything else
in the written manifest is read from the files.
"""

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
    ImageEntry(
        id="sdxl-turbo",
        name="SDXL Turbo",
        family="Stable Diffusion",
        publisher="Stability AI",
        description="XL quality in one step, for quick drafts. Non-commercial licence.",
        # Non-commercial and research use; commercial use needs a Stability AI
        # membership.
        license="sai-nc-community",
        source_repo="stabilityai/sdxl-turbo",
        repo="gpustack/stable-diffusion-xl-1.0-turbo-GGUF",
        aliases=("stabilityai/sdxl-turbo",),
        image={
            "origin": "stabilityai/sdxl-turbo model card",
            "resolution": 512,
            "steps": 1,
            "cfg": 0.0,
        },
        run_args=("--backend", "vae=cpu"),
    ),
)
