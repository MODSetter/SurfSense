"""Fetch a build's files into a folder, pinned and verified, then record it."""

from collections.abc import AsyncIterator
from pathlib import Path

from modules.llm.catalog.local.build import FileRole
from modules.llm.catalog.local.install.plan import InstallPlan
from modules.llm.catalog.local.installs import (
    InstalledBuild,
    projector_filename,
    record_install,
)
from modules.llm.providers.llamacpp import download_gguf
from modules.llm.providers.types import DownloadProgress

RESOLVE = "https://huggingface.co/{repo}/resolve/{revision}/{path}"


async def download_build(
    plan: InstallPlan, folder: Path
) -> AsyncIterator[DownloadProgress]:
    """Weights keep their own names; a projector takes the model's, so two
    vision models never share or overwrite one."""
    total = plan.build.footprint_bytes
    done = 0
    weights: list[str] = []
    projector: str | None = None
    for file in plan.build.files:
        if file.role is FileRole.PROJECTOR:
            name = projector_filename(plan.model_id)
            projector = name
        else:
            name = file.path.rsplit("/", 1)[-1]
            weights.append(name)
        url = RESOLVE.format(repo=file.repo, revision=file.revision, path=file.path)
        finished = 0
        async for step in download_gguf(url, folder / name, sha256=file.sha256):
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
        ),
    )
