"""Fetch a build's files into a folder, pinned and verified, recorded as each lands."""

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
    landings = [(file, landing(file)) for file in plan.build.files]
    weights: list[str] = []
    companions: list[str] = []
    projector: str | None = None
    for index, (file, name) in enumerate(landings):
        if not (
            file.sha256 and await asyncio.to_thread(_holds, folder / name, file.sha256)
        ):
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
        else:
            done += file.size_bytes
            yield DownloadProgress("downloading", done, total)
        if file.role is FileRole.WEIGHTS:
            weights.append(name)
        elif file.role is FileRole.PROJECTOR:
            projector = name
        else:
            companions.append(name)
        # The record after every file, naming the rest: a connection that drops
        # between two files leaves a build the catalog knows is unfinished.
        record_install(
            folder,
            InstalledBuild(
                model_id=plan.model_id,
                repo=plan.build.weights.repo,
                revision=plan.build.weights.revision,
                quantization=plan.build.quantization,
                weights=tuple(weights),
                projector=projector,
                projector_gguf=_projector_gguf(plan, projector),
                companions=tuple(companions),
                pending=tuple(n for _, n in landings[index + 1 :]),
            ),
        )


def _projector_gguf(plan: InstallPlan, landed: str | None) -> dict:
    """The projector's committed keys once it has landed, else nothing."""
    projector = plan.build.projector
    return dict(projector.gguf) if projector and landed else {}


def _holds(path: Path, sha256: str) -> bool:
    if not path.is_file():
        return False
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest() == sha256
