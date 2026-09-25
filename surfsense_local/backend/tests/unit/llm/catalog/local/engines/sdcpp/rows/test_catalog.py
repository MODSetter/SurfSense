"""The manifest's image models and the images folder, as rows that say nothing
about this machine: image models have no fit estimate.
"""

import pytest

from modules.llm.catalog.local.engines.sdcpp.rows.catalog import image_catalog
from modules.llm.catalog.local.manifest import load_local_manifest
from modules.llm.catalog.local.rows import LeadReason
from modules.llm.model_type import ModelType

pytestmark = pytest.mark.unit

MODELS = load_local_manifest().models


def rows(installs=None, files=(), selected=None):
    """The shipped manifest's image rows against a folder."""
    return {
        r.id: r
        for r in image_catalog(
            MODELS,
            installs or {},
            set(files),
            lambda b: f"id:{b.runtime_name}",
            selected=selected,
        )
    }


def test_every_curated_image_model_is_a_runnable_unpriced_row() -> None:
    """Offered by sd.cpp, downloadable, and never starred or badged."""
    result = rows()

    assert set(result) == {"stable-diffusion-1.5", "sdxl-base-1.0"}
    sd15 = result["stable-diffusion-1.5"]
    assert sd15.engine == "sdcpp"
    assert sd15.classification.types == (ModelType.IMAGE_GEN,)
    assert sd15.runnable and not sd15.recommended
    (build,) = sd15.builds
    assert build.fit is None and build.badge is None
    assert build.can_install
    assert build.installed_as is None
    assert sd15.lead is not None
    assert (sd15.lead.quantization, sd15.lead.why) == ("Q4_0", LeadReason.DEFAULT)


def test_a_build_an_install_record_names_is_installed_under_that_id() -> None:
    """How an adopted old download is found, whatever its file is called."""
    from modules.llm.catalog.local.engines.sdcpp.images_folder.legacy import adopt

    (record,) = adopt(["sd15-q4_0.gguf"], MODELS)

    sd15 = rows(installs={record.model_id: record})["stable-diffusion-1.5"]

    assert sd15.builds[0].installed_as == "v1-5-pruned_Q4_0"
    assert sd15.lead is not None and sd15.lead.why is LeadReason.INSTALLED


def test_a_build_whose_own_file_is_in_the_folder_is_installed() -> None:
    """A file copied in by hand under its published name."""
    sdxl = rows(files={"sd_xl_base_1.0_0_Q4_0.gguf"})["sdxl-base-1.0"]

    assert sdxl.builds[0].installed_as == "sd_xl_base_1.0_0_Q4_0"


def test_the_selected_image_model_leads_as_in_use() -> None:
    """The row says which build the Studio's images come from."""
    sdxl = rows(
        files={"sd_xl_base_1.0_0_Q4_0.gguf"},
        selected="sd_xl_base_1.0_0_Q4_0",
    )["sdxl-base-1.0"]

    assert sdxl.lead is not None and sdxl.lead.why is LeadReason.IN_USE
