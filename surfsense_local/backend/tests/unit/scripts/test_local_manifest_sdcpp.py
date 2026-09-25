"""An image model's manifest entry: evidence from its tensors, the rest from the
reviewed entry.
"""

from dataclasses import replace

import pytest
from local_manifest.recorded import RepoAtRevision
from local_manifest.sdcpp.assemble import entry_for, pinned_builds
from local_manifest.sdcpp.entry import Companion, ImageEntry, VideoEntry
from local_manifest.unreadable import UnreadableBuildError

from modules.llm.catalog.local.listed_file import ListedFile
from modules.llm.catalog.local.manifest import SCHEMA_VERSION, LocalManifest
from modules.llm.gguf import read_header_prefix
from tests.unit.llm.catalog.local.engines.sdcpp.builds.test_in_repo import REV
from tests.unit.llm.catalog.local.engines.sdcpp.test_evidence import (
    FLUX2_KLEIN_TENSORS,
    SDXL_TENSORS,
    WAN_TENSORS,
)
from tests.unit.llm.gguf.build import gguf, tensor

pytestmark = pytest.mark.unit

SHA = "1f64d77cbd8aee3ee1a0ae6e58ea64ba39308721150f38cfaa5ee57e9d4fd106"
ENTRY = ImageEntry(
    id="sdxl-base-1.0",
    name="Stable Diffusion XL",
    family="Stable Diffusion",
    publisher="Stability AI",
    description="Higher detail at 1024x1024, and slower.",
    license="openrail++",
    source_repo="stabilityai/stable-diffusion-xl-base-1.0",
    repo="kostakoff/stable-diffusion-xl-base-1.0-GGUF",
    image={
        "origin": "stabilityai/stable-diffusion-xl-base-1.0 model card",
        "resolution": 1024,
    },
    run_args=("--backend", "vae=cpu"),
)
SNAPSHOT = RepoAtRevision(
    ENTRY.repo,
    REV,
    "text-to-image",
    (
        ListedFile("README.md", 4014),
        ListedFile("sd_xl_base_1.0_0_Q4_0.gguf", 2709379488, SHA),
        ListedFile("sd_xl_base_1.0_0_Q8_0.gguf", 4180186816, "c" * 64),
    ),
    None,
)
HEADER = read_header_prefix(gguf([], [tensor(n, [4, 4]) for n in SDXL_TENSORS]))


def test_the_entry_validates_with_evidence_from_its_tensors() -> None:
    """The written entry is one the app loads, typed by what sd.cpp would see."""
    written = entry_for(ENTRY, SNAPSHOT, pinned_builds(ENTRY, SNAPSHOT), HEADER, {})

    (model,) = LocalManifest.model_validate(
        {
            "schema_version": SCHEMA_VERSION,
            "refreshed_at": "2026-09-23",
            "models": [written],
        }
    ).models
    assert model.evidence.architecture == "sdxl"
    assert model.evidence.pipeline_tag == "text-to-image"
    assert model.image is not None and model.image.resolution == 1024
    (build,) = model.builds
    assert build.quantization == "Q4_0"
    assert build.files[0].sha256 == SHA
    assert build.run.args == ["--backend", "vae=cpu"]


KLEIN = ImageEntry(
    id="flux2-klein-4b",
    name="FLUX.2 klein 4B",
    family="FLUX.2",
    publisher="Black Forest Labs",
    description="Makes and edits images in four steps.",
    license="apache-2.0",
    source_repo="black-forest-labs/FLUX.2-klein-4B",
    repo="leejet/FLUX.2-klein-4B-GGUF",
    image={"origin": "model card", "resolution": 1024, "steps": 4, "cfg": 1.0},
    builds=("Q4_0",),
    companions=(
        Companion("text_encoder", "unsloth/Qwen3-4B-GGUF", "Qwen3-4B-Q4_0.gguf"),
        Companion(
            "vae",
            "Comfy-Org/flux2-klein-4B",
            "split_files/vae/flux2-vae.safetensors",
            upstream_repo="black-forest-labs/FLUX.2-klein-4B",
        ),
    ),
)
ENCODER_REV, VAE_REV = "b" * 40, "c" * 40
KLEIN_REPO = RepoAtRevision(
    KLEIN.repo,
    REV,
    "text-to-image",
    (
        ListedFile("flux-2-klein-4b-Q4_0.gguf", 2460378560, "1" * 64),
        ListedFile("flux-2-klein-4b-Q8_0.gguf", 4300629440, "2" * 64),
    ),
    None,
)
COMPANION_REPOS = {
    "unsloth/Qwen3-4B-GGUF": RepoAtRevision(
        "unsloth/Qwen3-4B-GGUF",
        ENCODER_REV,
        "text-generation",
        (ListedFile("Qwen3-4B-Q4_0.gguf", 2375773472, "3" * 64),),
        None,
    ),
    "Comfy-Org/flux2-klein-4B": RepoAtRevision(
        "Comfy-Org/flux2-klein-4B",
        VAE_REV,
        None,
        (ListedFile("split_files/vae/flux2-vae.safetensors", 336211292, "4" * 64),),
        None,
    ),
}
KLEIN_HEADER = read_header_prefix(
    gguf([], [tensor(n, [4, 4]) for n in FLUX2_KLEIN_TENSORS])
)


def test_a_build_carries_its_companions_each_pinned_where_it_lies() -> None:
    """The text encoder and the VAE come from their own repos, at their own
    commits, and a mirror names the vendor it copies."""
    builds = pinned_builds(KLEIN, KLEIN_REPO, COMPANION_REPOS)
    written = entry_for(KLEIN, KLEIN_REPO, builds, KLEIN_HEADER, {})

    (model,) = LocalManifest.model_validate(
        {
            "schema_version": SCHEMA_VERSION,
            "refreshed_at": "2026-09-25",
            "models": [written],
        }
    ).models
    assert model.evidence.architecture == "flux2"
    (build,) = model.builds
    assert [(f.role, f.repo, f.revision) for f in build.files] == [
        ("weights", KLEIN.repo, REV),
        ("text_encoder", "unsloth/Qwen3-4B-GGUF", ENCODER_REV),
        ("vae", "Comfy-Org/flux2-klein-4B", VAE_REV),
    ]
    assert build.files[0].upstream_repo is None
    assert build.files[2].upstream_repo == "black-forest-labs/FLUX.2-klein-4B"


def test_only_the_builds_the_entry_names_are_pinned_in_its_order() -> None:
    """The first is the default a row downloads."""
    entry = replace(KLEIN, builds=("Q8_0", "Q4_0"))

    builds = pinned_builds(entry, KLEIN_REPO, COMPANION_REPOS)

    assert [b.quantization for b in builds] == ["Q8_0", "Q4_0"]


def test_a_companion_its_repo_no_longer_lists_refuses_the_refresh() -> None:
    """Nothing is written that could not be downloaded as pinned."""
    moved = dict(COMPANION_REPOS)
    moved["Comfy-Org/flux2-klein-4B"] = replace(
        COMPANION_REPOS["Comfy-Org/flux2-klein-4B"], listing=()
    )

    with pytest.raises(UnreadableBuildError, match="flux2-vae"):
        pinned_builds(KLEIN, KLEIN_REPO, moved)


WAN = VideoEntry(
    id="wan2.1-t2v-1.3b",
    name="Wan2.1 T2V 1.3B",
    family="Wan",
    publisher="Wan-AI",
    description="Short clips from text, in the least memory.",
    license="apache-2.0",
    source_repo="Wan-AI/Wan2.1-T2V-1.3B",
    repo="samuelchristlie/Wan2.1-T2V-1.3B-GGUF",
    builds=("Q8_0",),
    companions=(
        Companion(
            "text_encoder",
            "city96/umt5-xxl-encoder-gguf",
            "umt5-xxl-encoder-Q4_K_M.gguf",
        ),
    ),
    video={"origin": "model card", "frames": 33, "fps": 16},
)
WAN_REPO = RepoAtRevision(
    WAN.repo,
    REV,
    "text-to-video",
    (ListedFile("Wan2.1-T2V-1.3B-Q8_0.gguf", 1535768800, "5" * 64),),
    None,
)
UMT5 = {
    "city96/umt5-xxl-encoder-gguf": RepoAtRevision(
        "city96/umt5-xxl-encoder-gguf",
        ENCODER_REV,
        None,
        (ListedFile("umt5-xxl-encoder-Q4_K_M.gguf", 3655145312, "6" * 64),),
        None,
    )
}


def test_a_video_entry_writes_its_clip_defaults_in_place_of_image_ones() -> None:
    """The same assembly as an image model's; only the reviewed block differs."""
    header = read_header_prefix(gguf([], [tensor(n, [4, 4]) for n in WAN_TENSORS]))
    written = entry_for(WAN, WAN_REPO, pinned_builds(WAN, WAN_REPO, UMT5), header, {})

    assert "image" not in written
    (model,) = LocalManifest.model_validate(
        {
            "schema_version": SCHEMA_VERSION,
            "refreshed_at": "2026-09-25",
            "models": [written],
        }
    ).models
    assert model.evidence.architecture == "wan"
    assert model.video is not None and model.video.frames == 33


def test_an_entry_can_take_its_builds_from_one_folder_of_the_repo() -> None:
    """LongCat's repo holds two conversions; sd.cpp's docs cite the comfy/ one."""
    longcat = replace(
        KLEIN,
        id="longcat-image",
        repo="vantagewithai/LongCat-Image-GGUF",
        folder="comfy",
    )
    listing = RepoAtRevision(
        longcat.repo,
        REV,
        "text-to-image",
        (
            ListedFile("comfy/LongCat-Image-Q4_0.gguf", 3591090400, "7" * 64),
            ListedFile("org/LongCat-Image-Q4_0.gguf", 3556481696, "8" * 64),
        ),
        None,
    )

    (build,) = pinned_builds(longcat, listing, COMPANION_REPOS)

    assert build.weights.path == "comfy/LongCat-Image-Q4_0.gguf"
