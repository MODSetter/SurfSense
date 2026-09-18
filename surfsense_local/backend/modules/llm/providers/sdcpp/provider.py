"""The bundled sd-server: local image models, downloaded when asked for.

Electron owns the process and cannot start it until weights are on disk, because
sd-server names its model with -m and exits without one. It holds exactly one
model, so choosing another restarts it; /llm/image/local/runtime is what Electron
reconciles against. This module is the catalogue and the downloads, not a runtime.

Every entry is a single self-contained GGUF. Models that need their text encoders
downloaded alongside (SD 3.5's "pure" builds, FLUX) do not fit that contract and
are left out rather than half-supported.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path

import httpx

from modules.llm.providers.types import DownloadProgress
from shared.config import get_llm_settings

PROVIDER = "sdcpp"

# Multi-GB over a home connection: minutes, not seconds.
DOWNLOAD_TIMEOUT = httpx.Timeout(3600.0, connect=10.0)
CHUNK_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True)
class ImageModel:
    name: str
    label: str
    detail: str
    file: str
    url: str
    size_bytes: int
    sha256: str
    # Extra sd-server flags. SDXL's VAE decode alone can want ~10 GB of VRAM,
    # so it decodes on the CPU and the card only holds the diffusion model.
    args: tuple[str, ...] = field(default_factory=tuple)


CATALOG: tuple[ImageModel, ...] = (
    ImageModel(
        name="stable-diffusion-1.5",
        label="Stable Diffusion 1.5",
        detail="Fastest, lowest memory. 512x512.",
        file="sd15-q4_0.gguf",
        url=(
            "https://huggingface.co/kostakoff/stable-diffusion-v1-5-GGUF"
            "/resolve/main/v1-5-pruned_Q4_0.gguf"
        ),
        size_bytes=3_051_366_272,
        sha256="24bcd54c1d1f0354a1cd19d07ad9a20771d43fde8318d505d71bcd84b078f20a",
    ),
    # size_bytes is the label on the download button and the progress total; the
    # SHA is what decides whether the bytes were right. Both come from the
    # repository's file listing, never from a rounded size.
    ImageModel(
        name="sdxl-base-1.0",
        label="Stable Diffusion XL",
        detail="Higher detail at 1024x1024, and slower.",
        file="sdxl-base-q4_0.gguf",
        url=(
            "https://huggingface.co/kostakoff/stable-diffusion-xl-base-1.0-GGUF"
            "/resolve/main/sd_xl_base_1.0_0_Q4_0.gguf"
        ),
        size_bytes=2_709_379_488,
        sha256="1f64d77cbd8aee3ee1a0ae6e58ea64ba39308721150f38cfaa5ee57e9d4fd106",
        args=("--backend", "vae=cpu"),
    ),
    ImageModel(
        name="sdxl-turbo",
        label="SDXL Turbo",
        detail="XL quality in few steps, for quicker drafts.",
        file="sdxl-turbo-q4_0.gguf",
        url=(
            "https://huggingface.co/gpustack/stable-diffusion-xl-1.0-turbo-GGUF"
            "/resolve/main/stable-diffusion-xl-1.0-turbo-Q4_0.gguf"
        ),
        size_bytes=3_940_010_720,
        sha256="5282eec23430ca46de87de984521fbf04e3cf78fa4152b05610089bc71d8a535",
        args=("--backend", "vae=cpu"),
    ),
)


def model_dir() -> Path | None:
    return get_llm_settings().image_models_dir


def offered() -> bool:
    """False where Electron staged no sd-server, so nothing is advertised."""
    return model_dir() is not None


def find(name: str) -> ImageModel | None:
    return next((model for model in CATALOG if model.name == name), None)


def path_of(model: ImageModel) -> Path | None:
    directory = model_dir()
    return directory / model.file if directory is not None else None


def installed(model: ImageModel) -> bool:
    """Presence is the gate, because only install() writes this name.

    It downloads to a .part file, checks the SHA-256, and renames, so a file
    under the real name is whole. Comparing against size_bytes instead would
    make a stale byte count in the catalogue read as "never downloaded",
    silently and forever.
    """
    path = path_of(model)
    return path is not None and path.is_file() and path.stat().st_size > 0


def base_url() -> str:
    """Where sd-server answers, once it is running."""
    return f"{get_llm_settings().image_base_url.rstrip('/')}/v1"


async def install(model: ImageModel) -> AsyncIterator[DownloadProgress]:
    """Download weights, hashing as they arrive, and publish them at the end.

    Writes to a .part file and renames, because Electron starts sd-server as soon
    as the real name appears and would otherwise load a partial file.
    """
    path = path_of(model)
    if path is None:
        raise RuntimeError("this build has no local image support")
    if installed(model):
        yield DownloadProgress("success", model.size_bytes, model.size_bytes)
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".part")
    digest = sha256()
    written = 0

    try:
        async with (
            httpx.AsyncClient(
                timeout=DOWNLOAD_TIMEOUT, follow_redirects=True
            ) as client,
            client.stream("GET", model.url) as reply,
        ):
            reply.raise_for_status()
            total = int(reply.headers.get("content-length") or model.size_bytes)
            with partial.open("wb") as sink:
                async for chunk in reply.aiter_bytes(CHUNK_BYTES):
                    sink.write(chunk)
                    digest.update(chunk)
                    written += len(chunk)
                    yield DownloadProgress("downloading", written, total)

        if digest.hexdigest() != model.sha256:
            raise RuntimeError(f"{model.label} failed its checksum")
        partial.replace(path)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise

    yield DownloadProgress("success", written, written)


def remove(model: ImageModel) -> None:
    path = path_of(model)
    if path is not None:
        path.unlink(missing_ok=True)
