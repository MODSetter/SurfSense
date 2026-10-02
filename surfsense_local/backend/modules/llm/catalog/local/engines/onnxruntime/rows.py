"""The manifest's embedders as rows, unpriced: an embedder is small beside a chat
model, and its size is what the screen shows."""

from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import replace

from modules.embedding.spec import EmbedderSpec
from modules.llm.catalog.local.build import Build, BuildFile, FileRole
from modules.llm.catalog.local.classifier import classify
from modules.llm.catalog.local.engines.onnxruntime import ENGINE
from modules.llm.catalog.local.engines.registry import engine_for
from modules.llm.catalog.local.installs import InstalledBuild
from modules.llm.catalog.local.manifest import CuratedModel
from modules.llm.catalog.local.rows import (
    BuildRow,
    Lead,
    LeadReason,
    LocalRow,
    LocalSupport,
    Origin,
)


def embedding_catalog(
    models: Sequence[CuratedModel],
    installs: Mapping[str, InstalledBuild],
    catalog_id: Callable[[Build], str],
    *,
    bundled: Collection[str] = (),
) -> list[LocalRow]:
    """`installs` is keyed by catalog id, which is what a download is named;
    `bundled` names the ones the app ships, installed from the first start."""
    rows = []
    for model in models:
        classification = classify(
            model.evidence.architecture, model.evidence.pipeline_tag
        )
        engine = engine_for(classification.types)
        if engine is None or engine.name != ENGINE:
            continue
        installed = model.id in bundled or (
            model.id in installs and not installs[model.id].pending
        )
        build_rows = tuple(
            BuildRow(
                catalog_id=catalog_id(build),
                build=build,
                fit=None,
                badge=None,
                installed_as=model.id if installed else None,
                recommended=False,
                reads_images=False,
                projector_checked=False,
                bundled=model.id in bundled,
            )
            for build in model.as_builds()
        )
        lead = build_rows[0].build.quantization
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
                default_quantization=lead,
                recommended=False,
                engine=ENGINE,
                lead=Lead(
                    lead, LeadReason.INSTALLED if installed else LeadReason.DEFAULT
                ),
                description=model.description,
            )
        )
    return rows


def downloaded_rows(specs: Sequence[EmbedderSpec]) -> list[LocalRow]:
    """Hugging Face picks on disk: installed, with nothing left to download."""
    classification = classify("", "feature-extraction")
    rows = []
    for spec in specs:
        build = Build(
            "ONNX",
            (
                BuildFile(FileRole.WEIGHTS, spec.weights.path, 0, spec.weights.sha256),
                BuildFile(
                    FileRole.TOKENIZER, spec.tokenizer.path, 0, spec.tokenizer.sha256
                ),
            ),
        )
        rows.append(
            LocalRow(
                id=spec.id,
                origin=Origin.DOWNLOADED,
                name=spec.repo,
                family="Hugging Face",
                classification=classification,
                support=LocalSupport(
                    context=None, reads_images=False, tools=None, reasoning=None
                ),
                builds=(
                    BuildRow(
                        catalog_id="",
                        build=build,
                        fit=None,
                        badge=None,
                        installed_as=spec.id,
                        recommended=False,
                        reads_images=False,
                        projector_checked=False,
                    ),
                ),
                default_quantization="ONNX",
                recommended=False,
                engine=ENGINE,
                lead=Lead("ONNX", LeadReason.INSTALLED),
            )
        )
    return rows


def searched_row(repo: str, build: BuildRow | None, reason: str | None) -> LocalRow:
    """One opened Hugging Face repo, in the shape the GGUF search answers: its
    one build, or none and why."""
    classification = classify("", "feature-extraction")
    if build is None:
        # No build to offer: classified as nothing, so the row says why.
        classification = replace(
            classification,
            types=(),
            reason=reason or "SurfSense cannot run this model.",
        )
    return LocalRow(
        id=repo,
        origin=Origin.SEARCH,
        name=repo,
        family="Hugging Face",
        classification=classification,
        support=LocalSupport(
            context=None, reads_images=False, tools=None, reasoning=None
        ),
        builds=(build,) if build else (),
        default_quantization=build.build.quantization if build else None,
        recommended=False,
        engine=ENGINE,
    )
