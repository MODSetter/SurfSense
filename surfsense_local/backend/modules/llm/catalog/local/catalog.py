"""The manifest and the models folder in, the screen's local rows out.

Pure: no network and no disk, so every rule is a unit test. A downloaded file
that is a curated build (its install record names one of the model's repos, or
its name is the build's own file) shows as that curated row, installed; any
other file is its own row, judged from its header alone.
"""

import dataclasses
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from modules.llm.catalog.local.build_choice import default_build, recommended_build
from modules.llm.catalog.local.builds import Build, BuildFile, FileRole
from modules.llm.catalog.local.classifier import classify
from modules.llm.catalog.local.downloaded import DownloadedModel
from modules.llm.catalog.local.lead_build import lead_build
from modules.llm.catalog.local.manifest import CuratedModel
from modules.llm.catalog.local.pricing import price
from modules.llm.catalog.local.quantization import quantization_label
from modules.llm.catalog.local.recommendation import recommended_model
from modules.llm.catalog.local.rows import BuildRow, LocalRow, Origin
from modules.llm.catalog.local.support import (
    LocalSupport,
    projector_fits_model,
    projector_reads_images,
    template_support,
)
from modules.llm.fit import FitState, HardwareBudget, badge, speed_tier

_STATE_ORDER = {FitState.FITS: 0, FitState.PARTIAL: 1, FitState.TOO_BIG: 2}


@dataclass(frozen=True)
class LocalCatalog:
    rows: tuple[LocalRow, ...]
    recommended_id: str | None


def local_catalog(
    models: Sequence[CuratedModel],
    downloaded: Sequence[DownloadedModel],
    budget: HardwareBudget,
    catalog_id: Callable[[Build], str],
    *,
    selected: str | None = None,
) -> LocalCatalog:
    claimed: set[str] = set()
    curated = []
    for model in models:
        row, installed = _curated_row(model, downloaded, budget, catalog_id)
        claimed |= installed
        curated.append(row)
    star = recommended_model(curated)
    others = [
        _downloaded_row(d, budget) for d in downloaded if d.model_id not in claimed
    ]

    def led(row: LocalRow) -> LocalRow:
        lead = lead_build(row.builds, row.default_quantization, selected=selected)
        return dataclasses.replace(row, recommended=row.id == star, lead=lead)

    curated = [led(row) for row in curated]
    # By the fit of the build each row shows, coarsely, then list position: a
    # refused 32B at the top of a small machine's screen is the one thing a
    # model chooser must not do.
    order = {row.id: i for i, row in enumerate(curated)}
    curated.sort(key=lambda r: (_lead_state(r), order[r.id]))
    rows = tuple(curated + [led(row) for row in others])
    return LocalCatalog(rows, star)


def _curated_row(
    model: CuratedModel,
    downloaded: Sequence[DownloadedModel],
    budget: HardwareBudget,
    catalog_id: Callable[[Build], str],
) -> tuple[LocalRow, set[str]]:
    builds = model.as_builds()
    shape = model.model_shape
    fits = {
        b.quantization: price(
            shape, b.weights_bytes, b.projector.size_bytes if b.projector else 0, budget
        )
        for b in builds
    }
    default = default_build(builds)
    pick = recommended_build(
        builds, default, lambda b: speed_tier(fits[b.quantization])
    )
    repos = {
        model.source_repo,
        *model.aliases,
        *(f.repo for b in builds for f in b.files),
    }

    installed: set[str] = set()
    rows = []
    for build in builds:
        on_disk = _installed_as(build, repos, downloaded)
        if on_disk:
            installed.add(on_disk)
        reads = build.projector is not None and projector_reads_images(
            build.projector.gguf
        )
        fit = fits[build.quantization]
        rows.append(
            BuildRow(
                catalog_id=catalog_id(build),
                build=build,
                fit=fit,
                badge=badge(fit, budget),
                installed_as=on_disk,
                recommended=build is pick,
                reads_images=reads,
                projector_checked=True,
            )
        )
    tools, reasoning = model.template.tools, model.template.reasoning
    classification = classify(model.evidence.architecture, model.evidence.pipeline_tag)
    return (
        LocalRow(
            id=model.id,
            origin=Origin.CURATED,
            name=model.name,
            family=model.family,
            classification=classification,
            support=LocalSupport(
                context=model.context,
                reads_images=any(r.reads_images for r in rows),
                tools=tools,
                reasoning=reasoning,
            ),
            builds=tuple(rows),
            default_quantization=default.quantization if default else None,
            recommended=False,
        ),
        installed,
    )


def _installed_as(
    build: Build, repos: set[str], downloaded: Sequence[DownloadedModel]
) -> str | None:
    """The runtime's name for this build if it is on disk, or None."""
    basename = build.weights.path.rsplit("/", 1)[-1]
    for d in downloaded:
        record = d.record
        if record is not None:
            if record.repo in repos and record.quantization == build.quantization:
                return d.model_id
        elif d.path.name == basename:
            return d.model_id
    return None


def _downloaded_row(d: DownloadedModel, budget: HardwareBudget) -> LocalRow:
    """A file in no manifest: its own header is the only evidence."""
    reads = (
        d.projector is not None
        and projector_reads_images(d.projector_kv)
        and projector_fits_model(d.projector_kv, d.model_kv)
    )
    projector_bytes = d.projector_bytes if reads else 0
    fit = price(d.shape, d.weights_bytes, projector_bytes, budget)
    files = (BuildFile(FileRole.WEIGHTS, d.path.name, d.weights_bytes),)
    if reads and d.projector is not None:
        files += (
            BuildFile(
                FileRole.PROJECTOR,
                d.projector.name,
                projector_bytes,
                gguf=d.projector_kv,
            ),
        )
    quantization = (
        d.record.quantization if d.record else quantization_label(d.path.name)
    )
    tools, reasoning = template_support(d.template)
    return LocalRow(
        id=d.model_id,
        origin=Origin.DOWNLOADED,
        name=d.model_id,
        family="",
        classification=d.classification,
        support=LocalSupport(
            context=d.shape.context_length
            if d.shape and d.shape.context_length
            else None,
            reads_images=reads,
            tools=tools,
            reasoning=reasoning,
        ),
        builds=(
            BuildRow(
                catalog_id="",
                build=Build(quantization, files),
                fit=fit,
                badge=badge(fit, budget),
                installed_as=d.model_id,
                recommended=False,
                reads_images=reads,
                projector_checked=d.projector is not None,
            ),
        ),
        default_quantization=None,
        recommended=False,
    )


def _lead_state(row: LocalRow) -> int:
    lead = next(
        (
            b
            for b in row.builds
            if row.lead and b.build.quantization == row.lead.quantization
        ),
        None,
    )
    return _STATE_ORDER[lead.fit.state] if lead else len(_STATE_ORDER)
