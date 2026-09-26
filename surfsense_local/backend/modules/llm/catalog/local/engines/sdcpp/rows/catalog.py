"""The manifest's image models and the images folder as rows, unpriced."""

from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import replace

from modules.llm.catalog.local.build import Build
from modules.llm.catalog.local.classifier import classify
from modules.llm.catalog.local.engines.registry import engine_for
from modules.llm.catalog.local.engines.sdcpp import ENGINE
from modules.llm.catalog.local.engines.sdcpp.builds.choice import default_build
from modules.llm.catalog.local.engines.sdcpp.images_folder.landing import landing
from modules.llm.catalog.local.engines.sdcpp.rows.lead_build import lead_build
from modules.llm.catalog.local.engines.sdcpp.tasks import model_types
from modules.llm.catalog.local.installs import InstalledBuild
from modules.llm.catalog.local.manifest import CuratedModel
from modules.llm.catalog.local.rows import BuildRow, LocalRow, LocalSupport, Origin


def image_catalog(
    models: Sequence[CuratedModel],
    installs: Mapping[str, InstalledBuild],
    files: Collection[str],
    catalog_id: Callable[[Build], str],
    *,
    selected: str | None = None,
) -> list[LocalRow]:
    rows = []
    for model in models:
        classification = classify(
            model.evidence.architecture, model.evidence.pipeline_tag
        )
        engine = engine_for(classification.types)
        if engine is None or engine.name != ENGINE:
            continue
        # What it is for is the entry's word, not the architecture's.
        classification = replace(classification, types=model_types(model))
        builds = model.as_builds()
        repos = {model.source_repo, *model.aliases, *(b.weights.repo for b in builds)}
        build_rows = tuple(
            BuildRow(
                catalog_id=catalog_id(build),
                build=build,
                fit=None,
                badge=None,
                installed_as=_installed_as(build, repos, installs, files),
                recommended=False,
                reads_images=False,
                projector_checked=False,
                download_bytes=sum(
                    f.size_bytes for f in build.files if landing(f) not in files
                ),
            )
            for build in builds
        )
        default = default_build(builds)
        default_quantization = default.quantization if default else None
        rows.append(
            LocalRow(
                id=model.id,
                origin=Origin.CURATED,
                name=model.name,
                family=model.family,
                classification=classification,
                support=LocalSupport(
                    context=None, reads_images=False, tools=None, reasoning=None
                ),
                builds=build_rows,
                default_quantization=default_quantization,
                recommended=False,
                engine=ENGINE,
                lead=lead_build(build_rows, default_quantization, selected=selected),
            )
        )
    return rows


def _installed_as(
    build: Build,
    repos: set[str],
    installs: Mapping[str, InstalledBuild],
    files: Collection[str],
) -> str | None:
    """Installed only while every file is on disk: sd-server is never started
    on half a model, and Download fetches what is missing."""
    for record in installs.values():
        if record.repo in repos and record.quantization == build.quantization:
            present = all(name in files for name in record.files)
            return record.model_id if present else None
    if all(landing(f) in files for f in build.files):
        return build.runtime_name
    return None
