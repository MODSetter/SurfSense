"""An installed image model as sd-server is launched on it: each file on its
own flag, and the model's reviewed defaults as the server's."""

import pytest

from modules.llm.catalog.local.engines.sdcpp.engine import SdCppEngine
from modules.llm.catalog.local.engines.sdcpp.images_folder.landing import landing
from modules.llm.catalog.local.manifest import load_local_manifest
from tests.unit.llm.catalog.local.engines.sdcpp.rows.test_catalog import (
    ENCODER_SHA,
    two_repo_model,
)

pytestmark = pytest.mark.unit


def put(folder, *names: str) -> None:
    """Files on disk under these names, as a download leaves them."""
    for name in names:
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(b"x")


def test_a_one_file_model_runs_from_that_file_at_its_own_size(tmp_path) -> None:
    """SD 1.5 carries its VAE and text encoder inside, so -m is all it takes."""
    put(tmp_path, "v1-5-pruned_Q4_0.gguf")

    image = SdCppEngine(tmp_path, load_local_manifest().models).installed_image(
        "v1-5-pruned_Q4_0"
    )

    assert image is not None
    assert image.files == (("-m", "v1-5-pruned_Q4_0.gguf"),)
    assert image.args[:4] == ("-W", "512", "-H", "512")


def test_each_file_of_a_split_model_goes_to_its_own_flag(tmp_path) -> None:
    """The server's defaults are the model's, since Studio posts only a prompt."""
    model = two_repo_model()
    put(tmp_path, *(landing(f) for f in model.as_builds()[0].files))

    image = SdCppEngine(tmp_path, [model]).installed_image("klein-Q4_0")

    assert image is not None
    assert image.files == (
        ("--diffusion-model", "klein-Q4_0.gguf"),
        ("--llm", f"shared/{ENCODER_SHA[:12]}-Qwen3-4B-Q4_0.gguf"),
        ("--vae", f"shared/{'3' * 12}-flux2-vae.safetensors"),
    )
    assert image.args == ("-W", "1024", "-H", "1024", "--steps", "4")


def test_a_model_missing_one_of_its_files_is_not_installed(tmp_path) -> None:
    """Its row offers Download, which fetches only what is missing, and
    sd-server is never started on half a model."""
    model = two_repo_model()
    put(tmp_path, "klein-Q4_0.gguf")
    engine = SdCppEngine(tmp_path, [model])

    (row,) = engine.rows([model], lambda b: "id", selected=None)

    assert row.builds[0].installed_as is None
    assert row.builds[0].download_bytes == 730
    assert engine.installed_image("klein-Q4_0") is None


def test_a_video_model_runs_with_its_clip_settings(tmp_path) -> None:
    """Wan's text encoder is T5, so it goes to --t5xxl; frames and rate are
    the server's own until a request says otherwise."""
    from modules.llm.catalog.local.manifest import CuratedModel
    from modules.llm.model_type import ModelType
    from tests.unit.llm.catalog.local.test_manifest import video_entry

    wan = CuratedModel.model_validate(video_entry())
    put(tmp_path, *(landing(f) for f in wan.as_builds()[0].files))

    video = SdCppEngine(tmp_path, [wan]).installed_image("Wan2.1-T2V-1.3B-Q8_0")

    assert video is not None
    assert [flag for flag, _ in video.files] == [
        "--diffusion-model",
        "--t5xxl",
        "--vae",
    ]
    assert video.args == (
        "-W",
        "832",
        "-H",
        "480",
        "--video-frames",
        "33",
        "--fps",
        "16",
        "--cfg-scale",
        "6.0",
        "--flow-shift",
        "3.0",
    )
    assert video.types == (ModelType.VIDEO_GEN,)


def test_longcat_runs_on_its_qwen_encoder_with_its_own_settings(tmp_path) -> None:
    """The curated entry as written: its text encoder on --llm, 50 steps."""
    longcat = next(m for m in load_local_manifest().models if m.id == "longcat-image")
    put(tmp_path, *(landing(f) for f in longcat.as_builds()[0].files))

    image = SdCppEngine(tmp_path, [longcat]).installed_image("LongCat-Image-Q4_0")

    assert image is not None
    assert [flag for flag, _ in image.files] == ["--diffusion-model", "--llm", "--vae"]
    assert image.files[0][1] == "LongCat-Image-Q4_0.gguf"
    assert image.args[4:6] == ("--steps", "50")
