"""Fetch a build's files into a folder, pinned and verified, then record it."""

import asyncio
import hashlib
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import httpx

from modules.llm.catalog.local.build import BuildFile, FileRole
from modules.llm.catalog.local.install.plan import InstallPlan
from modules.llm.catalog.local.installs import InstalledBuild, record_install
from modules.llm.providers.llamacpp import download_gguf
from modules.llm.providers.types import DownloadProgress

RESOLVE = "https://huggingface.co/{repo}/resolve/{revision}/{path}"


async def download_build(
    plan: InstallPlan,
    folder: Path,
    landing: Callable[[BuildFile], str],
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> AsyncIterator[DownloadProgress]:
    """Each file lands where its engine says. One already there with its pinned
    hash is not fetched again: another model uses it, or an install left it
    before failing."""
    total = plan.build.footprint_bytes
    done = 0
    weights: list[str] = []
    companions: list[str] = []
    projector: str | None = None
    for file in plan.build.files:
        name = landing(file)
        if file.role is FileRole.WEIGHTS:
            weights.append(name)
        elif file.role is FileRole.PROJECTOR:
            projector = name
        else:
            companions.append(name)
        if file.sha256 and await asyncio.to_thread(_holds, folder / name, file.sha256):
            done += file.size_bytes
            yield DownloadProgress("downloading", done, total)
            continue
        url = RESOLVE.format(repo=file.repo, revision=file.revision, path=file.path)
        finished = 0
        async for step in download_gguf(
            url, folder / name, sha256=file.sha256, transport=transport
        ):
            finished = step.completed
            yield DownloadProgress(
                step.status, done + step.completed, max(total, done + step.total)
            )
        done += finished
    projector_file = plan.build.projector
    record_install(
        folder,
        InstalledBuild(
            model_id=plan.model_id,
            repo=plan.build.weights.repo,
            revision=plan.build.weights.revision,
            quantization=plan.build.quantization,
            weights=tuple(weights),
            projector=projector,
            projector_gguf=dict(projector_file.gguf) if projector_file else {},
            companions=tuple(companions),
        ),
    )


def _holds(path: Path, sha256: str) -> bool:
    if not path.is_file():
        return False
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest() == sha256
