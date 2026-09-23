"""Image models the old hard-coded list downloaded keep working where they lie."""

import pytest

from modules.llm.catalog.local.engines.sdcpp.images_folder.legacy import adopt
from modules.llm.catalog.local.manifest import load_local_manifest

pytestmark = pytest.mark.unit

MANIFEST = load_local_manifest()


def test_a_file_the_old_list_downloaded_is_recorded_as_its_curated_build() -> None:
    """Recorded, not renamed: sd-server may hold the file open."""
    (record,) = adopt(["sd15-q4_0.gguf", "notes.txt"], MANIFEST.models)

    assert record.model_id == "v1-5-pruned_Q4_0"
    assert record.weights == ("sd15-q4_0.gguf",)
    assert record.repo == "kostakoff/stable-diffusion-v1-5-GGUF"
    assert record.quantization == "Q4_0"


def test_all_three_old_names_are_known() -> None:
    """Every model the old list offered."""
    records = adopt(
        ["sd15-q4_0.gguf", "sdxl-base-q4_0.gguf", "sdxl-turbo-q4_0.gguf"],
        MANIFEST.models,
    )

    assert sorted(r.model_id for r in records) == [
        "sd_xl_base_1.0_0_Q4_0",
        "stable-diffusion-xl-1.0-turbo-Q4_0",
        "v1-5-pruned_Q4_0",
    ]
