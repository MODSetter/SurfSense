"""An image model's manifest entry: evidence from its tensors, the rest from the
reviewed entry.
"""

import pytest
from local_manifest.recorded import RepoAtRevision
from local_manifest.sdcpp.assemble import entry_for, pinned_builds
from local_manifest.sdcpp.entry import ImageEntry

from modules.llm.catalog.local.listed_file import ListedFile
from modules.llm.catalog.local.manifest import SCHEMA_VERSION, LocalManifest
from modules.llm.gguf import read_header_prefix
from tests.unit.llm.catalog.local.engines.sdcpp.builds.test_in_repo import REV
from tests.unit.llm.catalog.local.engines.sdcpp.test_evidence import SDXL_TENSORS
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
    written = entry_for(ENTRY, SNAPSHOT, pinned_builds(SNAPSHOT), HEADER, {})

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
