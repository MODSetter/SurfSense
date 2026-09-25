"""The manifest's image models and the images folder, as rows that say nothing
about this machine: image models have no fit estimate.
"""

import pytest

from modules.llm.catalog.local.engines.sdcpp.rows.catalog import image_catalog
from modules.llm.catalog.local.manifest import CuratedModel, load_local_manifest
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
    """Offered by sd.cpp, downloadable, and never starred or badged; its video
    models beside them."""
    result = rows()

    images = {
        id
        for id, row in result.items()
        if ModelType.IMAGE_GEN in row.classification.types
    }
    assert images == {
        "flux2-klein-4b",
        "z-image-turbo",
        "ernie-image-turbo",
        "longcat-image",
        "stable-diffusion-1.5",
        "sdxl-base-1.0",
    }
    assert set(result) - images == {"wan2.1-t2v-1.3b", "wan2.2-ti2v-5b"}
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

    sd15 = rows(installs={record.model_id: record}, files={"sd15-q4_0.gguf"})[
        "stable-diffusion-1.5"
    ]

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


REV = "a" * 40
ENCODER_SHA = "e" * 64


def _file(role: str, repo: str, path: str, size: int, sha256: str) -> dict:
    return {
        "role": role,
        "repo": repo,
        "revision": REV,
        "path": path,
        "size_bytes": size,
        "sha256": sha256,
    }


def two_repo_model() -> CuratedModel:
    """A diffusion model whose text encoder and VAE come from other repos."""
    return CuratedModel.model_validate(
        {
            "id": "flux2-klein-4b",
            "name": "FLUX.2 klein 4B",
            "family": "FLUX.2",
            "publisher": "Black Forest Labs",
            "description": "Generates and edits in four steps.",
            "license": "apache-2.0",
            "source_repo": "black-forest-labs/FLUX.2-klein-4B",
            "evidence": {"architecture": "flux2"},
            "image": {"origin": "model card", "resolution": 1024, "steps": 4},
            "builds": [
                {
                    "quantization": "Q4_0",
                    "files": [
                        _file(
                            "weights",
                            "l/klein-GGUF",
                            "klein-Q4_0.gguf",
                            2_000,
                            "1" * 64,
                        ),
                        _file(
                            "text_encoder",
                            "u/Qwen3-4B-GGUF",
                            "Qwen3-4B-Q4_0.gguf",
                            700,
                            ENCODER_SHA,
                        ),
                        _file(
                            "vae",
                            "c/klein",
                            "split_files/vae/flux2-vae.safetensors",
                            30,
                            "3" * 64,
                        ),
                    ],
                }
            ],
        }
    )


def test_a_build_states_what_its_download_would_fetch() -> None:
    """A text encoder another model already brought is on disk, so it is not
    counted: the row says what Download will actually fetch."""
    encoder = f"shared/{ENCODER_SHA[:12]}-Qwen3-4B-Q4_0.gguf"

    (fresh,) = image_catalog([two_repo_model()], {}, set(), lambda b: "id")
    (after,) = image_catalog([two_repo_model()], {}, {encoder}, lambda b: "id")

    assert fresh.builds[0].download_bytes == 2_730
    assert after.builds[0].download_bytes == 2_030
    assert after.builds[0].build.footprint_bytes == 2_730


def test_a_recorded_build_whose_file_is_gone_is_not_installed() -> None:
    """Deleted by hand: the row offers Download again, not Use."""
    from modules.llm.catalog.local.engines.sdcpp.images_folder.legacy import adopt

    (record,) = adopt(["sd15-q4_0.gguf"], MODELS)

    sd15 = rows(installs={record.model_id: record})["stable-diffusion-1.5"]

    assert sd15.builds[0].installed_as is None


def test_z_image_after_flux2_klein_downloads_only_what_klein_did_not_bring() -> None:
    """They run with the same text encoder, pinned by the same hash."""
    from modules.llm.catalog.local.engines.sdcpp.images_folder.landing import landing

    klein = next(m for m in MODELS if m.id == "flux2-klein-4b").as_builds()[0]
    on_disk = {landing(f) for f in klein.files}

    zimage = rows(files=on_disk)["z-image-turbo"].builds[0]

    encoder = next(f for f in zimage.build.files if f.role.value == "text_encoder")
    assert zimage.download_bytes == zimage.build.footprint_bytes - encoder.size_bytes


def test_a_model_that_edits_too_fills_both_slots() -> None:
    """FLUX.2 klein edits with the weights it generates with; SD 1.5 cannot."""
    result = rows()

    klein = result["flux2-klein-4b"]
    assert klein.classification.types == (ModelType.IMAGE_GEN, ModelType.IMAGE_EDIT)
    assert klein.runnable
    assert result["stable-diffusion-1.5"].classification.types == (ModelType.IMAGE_GEN,)


def test_a_video_model_fills_the_video_slot_only() -> None:
    """Its entry's video block, not an image one, decides what it is for."""
    from tests.unit.llm.catalog.local.test_manifest import video_entry

    wan = CuratedModel.model_validate(video_entry())

    (row,) = image_catalog([wan], {}, set(), lambda b: "id")

    assert row.classification.types == (ModelType.VIDEO_GEN,)
    assert row.runnable
