"""Curated entries as rows a screen can render.

Priced entirely from the manifest: `shape` is committed, so this runs on first
paint with no network, no download and no scan. That is what makes the curated
tier the whole product on an airgapped machine.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from modules.llm.catalog.manifest import CuratedModel, Variant
from modules.llm.fit import (
    Badge,
    FitState,
    FitVerdict,
    HardwareBudget,
    ModelShape,
    badge,
    estimate,
    planned_precision,
)

_FIT_ORDER = {FitState.FITS: 0, FitState.PARTIAL: 1, FitState.TOO_BIG: 2}


@dataclass(frozen=True)
class CatalogRow:
    """One model on the screen.

    Deliberately carries no preference signal of its own. The manifest's own
    list order is what orders this list and selects the star, and it is never
    displayed; the surest way to keep that true is for the renderer never to
    receive it.
    """

    model_id: str
    label: str
    family: str
    parameter_count: str
    context_length: int
    architecture: str
    variant: Variant
    fit: FitVerdict
    badge: Badge
    capabilities: tuple[str, ...]

    @property
    def can_install(self) -> bool:
        """Only physics refuses. Reduced speed runs, so it never blocks."""
        return self.fit.state is not FitState.TOO_BIG


def curated_rows(
    models: Sequence[CuratedModel], budget: HardwareBudget
) -> list[CatalogRow]:
    """One row per model, best build first, ordered fit coarsely then manifest
    position finely.

    Position, not fit alone: sorting only by fit state would still leave two
    FITS rows in whatever order dict iteration happened to give them. A later
    position in `models` is preferred, matching the ladder's own order
    (smallest first, most capable last) — see `manifest.py`.
    """
    rows = [(index, _row(model, budget)) for index, model in enumerate(models)]
    return [
        row
        for _, row in sorted(
            rows,
            key=lambda pair: (
                _FIT_ORDER[pair[1].fit.state],
                -pair[0],
                pair[1].model_id,
            ),
        )
    ]


def _fit(shape: ModelShape, weights_bytes: int, budget: HardwareBudget) -> FitVerdict:
    """One build's verdict, at the cache the loader would give it."""
    precision = planned_precision(shape, weights_bytes, budget)
    return estimate(shape, weights_bytes, budget, precision=precision)


def _row(model: CuratedModel, budget: HardwareBudget) -> CatalogRow:
    """The best build of one model: a row is a model, not a file.

    A model with two builds is still one row, because the screen's job is
    choosing a model. It takes the best state among its builds, and the install
    action uses the build that produced it. A tie between two builds in the
    same fit state favours the one listed first in `variants` — the manifest's
    own order is the only preference signal, here as everywhere else in this
    module.
    """
    # Priced at the precision the loader will actually choose, not at the
    # default. Pricing f16 here while `plan_load` picks q8_0 badged a model
    # `Reduced speed` that the runtime then placed entirely on the device.
    priced = [
        (index, variant, _fit(model.model_shape, variant.size_bytes, budget))
        for index, variant in enumerate(model.variants)
    ]
    _, variant, fit = min(
        priced, key=lambda triple: (_FIT_ORDER[triple[2].state], triple[0])
    )
    return CatalogRow(
        model_id=model.model_id,
        label=model.label,
        family=model.family,
        parameter_count=model.parameter_count,
        context_length=model.shape.context_length,
        architecture=model.shape.architecture,
        variant=variant,
        fit=fit,
        badge=badge(fit, budget),
        capabilities=tuple(model.capabilities),
    )
