"""Curated entries as rows a screen can render.

Priced entirely from the manifest: `shape` is committed, so this runs on first
paint with no network, no download and no scan. That is what makes the curated
tier the whole product on an airgapped machine.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from modules.llm.catalog.manifest import CuratedModel, Variant
from modules.llm.fit import Badge, FitState, FitVerdict, HardwareBudget, badge, estimate

_FIT_ORDER = {FitState.FITS: 0, FitState.PARTIAL: 1, FitState.TOO_BIG: 2}


@dataclass(frozen=True)
class CatalogRow:
    """One model on the screen.

    Deliberately carries no `rank`. Rank orders this list and selects the star,
    and it is never displayed; the surest way to keep that true is for the
    renderer never to receive it.
    """

    model_id: str
    label: str
    family: str
    parameter_count: str
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
    """One row per model, best build first, ordered fit coarsely then rank finely.

    Sorting by rank alone would put a refused 32B at the top of a small machine's
    screen, which is the one thing a model chooser must not do.
    """
    rows = [_row(model, budget) for model in models]
    return sorted(
        rows,
        key=lambda row: (_FIT_ORDER[row.fit.state], -row.variant.rank, row.model_id),
    )


def _row(model: CuratedModel, budget: HardwareBudget) -> CatalogRow:
    """The best build of one model: a row is a model, not a file.

    A model with two builds is still one row, because the screen's job is
    choosing a model. It takes the best state among its builds, and the install
    action uses the build that produced it.
    """
    priced = [
        (variant, estimate(model.model_shape, variant.size_bytes, budget))
        for variant in model.variants
    ]
    variant, fit = min(
        priced, key=lambda pair: (_FIT_ORDER[pair[1].state], -pair[0].rank)
    )
    return CatalogRow(
        model_id=model.model_id,
        label=model.label,
        family=model.family,
        parameter_count=model.parameter_count,
        variant=variant,
        fit=fit,
        badge=badge(fit, budget),
        capabilities=tuple(model.capabilities),
    )
