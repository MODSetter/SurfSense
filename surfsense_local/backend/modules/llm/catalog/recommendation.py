"""Which curated build to star.

Gated on predicted speed rather than on full residency. Those coincide on a
large card and diverge on a small one: measured on an RTX 3050, Qwen3 8B spills
roughly a fifth and runs without noticeable lag, while a residency-only rule
stars a 1.7B on the same machine. That rule is not conservative, it is wrong,
because it bans a configuration that demonstrably works.

Eligibility is `speed.RECOMMENDABLE_TIERS`, not a threshold owned here. This
module used to draw its own line on `offload_fraction` (0.75) while `copy.py`
drew a different one (0.25, 0.5) to choose its wording, and nothing kept the
two in step: a build could be starred while its own badge said "expect it to
be slow". Reading the same tier both modules now share is what makes that
combination unrepresentable rather than merely untested.

The policy ranges over builds rather than models, because a build is what the
user installs. With one variant per entry the cross-product is the entry list
and the behaviour is identical, but writing it this way is the difference
between adding a second build later as a manifest edit and rewriting this
module, its tests and every fixture.

There is no quality score here either: preference is a candidate's position in
`curated`, the same list `rows.py` reads. The ladder is authored smallest to
largest, so "prefers a later entry" reads as "prefers the bigger model", with
nothing to keep in sync against a separate field.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from modules.llm.catalog.manifest import CuratedModel, Variant
from modules.llm.fit import HardwareBudget, estimate, planned_precision
from modules.llm.fit.estimate import FitVerdict
from modules.llm.fit.speed import RECOMMENDABLE_TIERS, speed_tier


@dataclass(frozen=True)
class Recommendation:
    entry: CuratedModel
    variant: Variant
    verdict: FitVerdict


def recommend(
    curated: Sequence[CuratedModel], budget: HardwareBudget
) -> Recommendation | None:
    """The build predicted fast enough that sits furthest down the ladder, or
    None.

    None is an honest answer rather than a failure: every build that physics does
    not refuse stays installable, it simply goes unstarred.
    """
    candidates: list[tuple[int, Recommendation]] = []
    for index, entry in enumerate(curated):
        for variant in entry.variants:
            # At the cache the loader would choose, so the gate judges the
            # configuration that will actually run rather than a slower one.
            precision = planned_precision(
                entry.model_shape, variant.size_bytes, budget
            )
            verdict = estimate(
                entry.model_shape, variant.size_bytes, budget, precision=precision
            )
            # TOO_BIG's own tier is never in RECOMMENDABLE_TIERS, so this is
            # the one check: physics and speed are both judged by the same
            # classification, not a state check plus a separate threshold.
            if speed_tier(verdict) not in RECOMMENDABLE_TIERS:
                continue
            candidates.append((index, Recommendation(entry, variant, verdict)))

    if not candidates:
        return None
    _, best = max(
        candidates, key=lambda pair: (pair[0], -pair[1].variant.size_bytes)
    )
    return best
