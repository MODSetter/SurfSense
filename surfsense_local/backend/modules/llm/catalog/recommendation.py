"""Which curated build to star.

Gated on predicted speed rather than on full residency. Those coincide on a
large card and diverge on a small one: measured on an RTX 3050, Qwen3 8B spills
roughly a fifth and runs without noticeable lag, while a residency-only rule
stars a 1.7B on the same machine. That rule is not conservative, it is wrong,
because it bans a configuration that demonstrably works.

The policy ranges over builds rather than models, because a build is what the
user installs and what `rank` describes. With one variant per entry the
cross-product is the entry list and the behaviour is identical, but writing it
this way is the difference between adding a second build later as a manifest
edit and rewriting this module, its tests and every fixture.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from modules.llm.catalog.manifest import CuratedModel, Variant
from modules.llm.fit import FitState, HardwareBudget, estimate, planned_precision
from modules.llm.fit.estimate import FitVerdict

# > ponytail: provisional, and possibly unnecessary. On the one machine measured
# > every offload fraction stayed usable: fully on the CPU the model still
# > decoded at 13 t/s, above reading pace, and prefill held at half device speed.
# > No threshold would have fired anywhere in the curated range. Check whether
# > this gate ever triggers before treating the number as load bearing; a
# > mechanism that never fires reads as protection that was never tested.
MAX_OFFLOAD = 0.75


@dataclass(frozen=True)
class Recommendation:
    entry: CuratedModel
    variant: Variant
    verdict: FitVerdict


def recommend(
    curated: Sequence[CuratedModel], budget: HardwareBudget
) -> Recommendation | None:
    """The highest-ranked build predicted fast enough, or None.

    None is an honest answer rather than a failure: every build that physics does
    not refuse stays installable, it simply goes unstarred.
    """
    candidates: list[Recommendation] = []
    for entry in curated:
        for variant in entry.variants:
            # At the cache the loader would choose, so the gate judges the
            # configuration that will actually run rather than a slower one.
            precision = planned_precision(
                entry.model_shape, variant.size_bytes, budget
            )
            verdict = estimate(
                entry.model_shape, variant.size_bytes, budget, precision=precision
            )
            if verdict.state is FitState.TOO_BIG:
                continue
            if verdict.offload_fraction > MAX_OFFLOAD:
                continue
            candidates.append(Recommendation(entry, variant, verdict))

    if not candidates:
        return None
    return max(candidates, key=lambda c: (c.variant.rank, -c.variant.size_bytes))
