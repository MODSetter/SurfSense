"""The exact answer for one searched build, read before any bytes move.

Opening a repo read no header; installing one build reads two: its weights (a
model, of which architecture, with what window) and its projector (does it see,
and does it belong to this model). A projector that fails is dropped rather than
installed beside a model it cannot serve.
"""

import dataclasses
from dataclasses import dataclass

import httpx

from modules.llm.catalog.local.builds import Build, BuildFile, FileRole
from modules.llm.catalog.local.classifier import Classification, classify
from modules.llm.catalog.local.pricing import exact_price
from modules.llm.catalog.local.support import (
    projector_fits_model,
    projector_reads_images,
)
from modules.llm.fit import FitVerdict, HardwareBudget
from modules.llm.gguf import header_from_url, to_shape
from modules.llm.gguf.file_kind import FileKind, kind_of

RESOLVE = "https://huggingface.co/{repo}/resolve/{revision}/{path}"


@dataclass(frozen=True)
class CheckedBuild:
    build: Build
    classification: Classification
    fit: FitVerdict
    reads_images: bool
    is_model: bool


def _url(file: BuildFile) -> str:
    return RESOLVE.format(repo=file.repo, revision=file.revision, path=file.path)


async def check_build(
    client: httpx.AsyncClient,
    build: Build,
    pipeline_tag: str | None,
    budget: HardwareBudget,
) -> CheckedBuild:
    header = await header_from_url(client, _url(build.weights))
    kind = kind_of(header)
    is_model = kind.kind is FileKind.MODEL or (
        kind.kind is FileKind.SHARD and int(header.metadata.get("split.no", 0)) == 0
    )
    classification = classify(kind.architecture, pipeline_tag)

    reads_images = False
    if build.projector is not None:
        projector = await header_from_url(client, _url(build.projector))
        reads_images = projector_reads_images(
            projector.metadata
        ) and projector_fits_model(projector.metadata, header.metadata)
        kept = dataclasses.replace(build.projector, gguf=dict(projector.metadata))
        files = tuple(f for f in build.files if f.role is FileRole.WEIGHTS)
        build = Build(build.quantization, files + ((kept,) if reads_images else ()))

    projector_bytes = build.projector.size_bytes if build.projector else 0
    fit = exact_price(to_shape(header), build.weights_bytes, projector_bytes, budget)
    return CheckedBuild(build, classification, fit, reads_images, is_model)
