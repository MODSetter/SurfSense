"""The staged sd.cpp server makes a picture: started the way the app starts it,
on a curated model, asked through the app's own image client.

`--help` and the platform floors show the server starts and links only what it
may. They do not show it can diffuse: a backend library pruned one file too
far, or a pin bump that renamed a tensor, passes both.

Opt-in, like the other packaging tests, and skipped unless
SURFSENSE_TEST_IMAGE_MODELS names a folder holding the curated model's weights
under their published name, checked against the manifest's sha256. Once it
does, a missing server (`pnpm build:sdcpp`, or SURFSENSE_TEST_SDCPP_DIR) fails
the run: CI sets the folder, and a skip there would pass unseen.
"""

import asyncio
import hashlib
import io
import os
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from PIL import Image

from modules.llm.catalog.local.engines.sdcpp.engine import SdCppEngine
from modules.llm.catalog.local.engines.sdcpp.images_folder.installed import (
    InstalledImage,
)
from modules.llm.catalog.local.installs import InstalledBuild, record_install
from modules.llm.catalog.local.manifest import load_local_manifest
from modules.llm.providers.openai_compatible.image import (
    OpenAICompatibleImageProvider,
)
from modules.llm.providers.sdcpp.serving import wait_until_serving

pytestmark = pytest.mark.packaging

ELECTRON = Path(__file__).resolve().parents[3] / "electron"
STAGED = Path(os.environ.get("SURFSENSE_TEST_SDCPP_DIR", ELECTRON / "sdcpp"))
MODELS_DIR = os.environ.get("SURFSENSE_TEST_IMAGE_MODELS")
SERVER = STAGED / ("sd-server.exe" if sys.platform == "win32" else "sd-server")

# The cheapest curated image model: one 3 GB file that carries its own VAE and
# text encoder.
MODEL_ID = "stable-diffusion-1.5"
# Not the entry's: enough steps for a picture, few enough for a runner with no
# graphics card. Everything else on the command line is what the app passes.
STEPS = 4

if MODELS_DIR is None:
    pytest.skip("needs SURFSENSE_TEST_IMAGE_MODELS", allow_module_level=True)

(CURATED,) = [m for m in load_local_manifest().models if m.id == MODEL_ID]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


@pytest.fixture(scope="module")
def installed(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, InstalledImage]:
    """The pinned build linked into an images folder and recorded, as an
    install leaves it, and read back the way the API reads it for Electron."""
    images = tmp_path_factory.mktemp("images")
    build = CURATED.builds[0]
    pinned = build.files[0]
    name = pinned.path.rsplit("/", 1)[-1]
    source = Path(MODELS_DIR) / name  # type: ignore[arg-type]
    assert _sha256(source) == pinned.sha256, f"{name} is not the pinned file"
    try:
        (images / name).symlink_to(source)
    except OSError:  # Windows without the symlink privilege
        shutil.copyfile(source, images / name)
    model_id = name.removesuffix(".gguf")
    record_install(
        images,
        InstalledBuild(
            model_id=model_id,
            repo=pinned.repo,
            revision=pinned.revision,
            quantization=build.quantization,
            weights=(name,),
        ),
    )
    image = SdCppEngine(images, [CURATED]).installed_image(model_id)
    assert image is not None, "the engine does not see the build as installed"
    return images, image


@pytest.fixture(scope="module")
def server_log(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Where the server writes; a test that fails shows its tail."""
    return tmp_path_factory.mktemp("server") / "sdcpp.log"


@pytest.fixture(scope="module")
def server(installed: tuple[Path, InstalledImage], server_log: Path) -> Iterator[str]:
    """The server as Electron's sidecar starts it (`sdcppSpec()` in
    `sidecars/sdcpp.ts`): each file on its flag, the port, `--diffusion-fa`,
    the entry's own arguments, from the staged folder."""
    images, image = installed
    assert SERVER.exists(), f"no staged sd.cpp server at {SERVER}"
    log = server_log.open("wb")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    files = [part for flag, path in image.files for part in (flag, str(images / path))]
    process = subprocess.Popen(
        [
            str(SERVER),
            *files,
            "--listen-port",
            str(port),
            "--diffusion-fa",
            *image.args,
            "--steps",
            str(STEPS),
        ],
        cwd=STAGED,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        process.terminate()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
        log.close()


async def _refuse_any_host(url: str) -> None:
    raise AssertionError(f"sd-server pointed at {url} for its image")


def test_the_staged_server_generates_a_picture(
    installed: tuple[Path, InstalledImage], server: str, server_log: Path
) -> None:
    """A PNG of the size the entry asks for that is not one flat colour."""
    _images, image = installed
    client = OpenAICompatibleImageProvider(
        0, f"{server}/v1", allow_url_host=_refuse_any_host
    )

    async def generate() -> bytes:
        await wait_until_serving(server, image.served_file, timeout=180.0)
        made = await client.generate(
            image.model_id,
            "a green parrot on a branch, blue sky, yellow flowers, photograph",
        )
        return made.content

    started = time.monotonic()
    try:
        content = asyncio.run(generate())
    except Exception:
        tail = server_log.read_text(errors="replace").splitlines()[-60:]
        sys.stderr.write("\n".join(["sd-server's log, last lines:", *tail]))
        raise
    # The run's cost, for whoever weighs this gate next (shown with `-s`).
    took = time.monotonic() - started
    sys.stderr.write(f"sd-server generated in {took:.0f} s at {STEPS} steps\n")

    assert CURATED.image is not None
    side = CURATED.image.resolution
    picture = Image.open(io.BytesIO(content))
    picture.load()  # decodes every pixel, not only the header
    assert picture.size == (side, side)
    # A blank canvas decodes and has the right size too. A picture has many
    # colours, spread across the frame: count them, and ask that no single one
    # covers most of it.
    colours = picture.convert("RGB").getcolors(maxcolors=side * side)
    assert colours is not None
    assert len(colours) > 1000, f"only {len(colours)} colours"
    most_common = max(count for count, _colour in colours)
    assert most_common < 0.5 * side * side, "one colour covers most of the image"
