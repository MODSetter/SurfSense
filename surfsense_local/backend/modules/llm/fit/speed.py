"""The one place `offload_fraction` becomes a decision.

A badge and a recommendation both start from the same `FitVerdict`, and both
used to threshold its raw `offload_fraction` independently: the badge drew
lines at a quarter and a half to choose its wording, the recommendation drew
a separate line at three quarters to choose whether to star a build. Nothing
connected the two, so a build could land in a badge's "expect it to be slow"
band while still being the one row the app steered someone toward.

Collapsing both into one ordered tier removes the second line rather than
moving it: a badge's wording and a recommendation's eligibility are now both
read off the same value, so they cannot disagree about the same verdict. Once
this exists, "should this be recommended" is answered without reference to
`offload_fraction` at all.
"""

from enum import StrEnum

from modules.llm.fit.budget import HardwareBudget
from modules.llm.fit.estimate import CONTEXT_RUNGS, FitVerdict
from modules.llm.fit.states import FitState

# The same quarter and half `copy.py` used to threshold on its own, moved here
# so nothing else can draw them differently. Below the first, most of the
# model is still resident; above the second, most of it is not.
_LIGHT_SPILL_CEILING = 0.25
_MODERATE_SPILL_CEILING = 0.5


class SpeedTier(StrEnum):
    """How a build will actually feel to use, worst to best.

    Ordered so a caller can compare tiers, though nothing here does yet; the
    order exists because "how good does this have to be to recommend" is a
    threshold on this scale, not a fact about any one member of it.
    """

    TOO_BIG = "too_big"
    HEAVY_SPILL = "heavy_spill"
    MODERATE_SPILL = "moderate_spill"
    LIGHT_SPILL = "light_spill"
    FULL = "full"


def speed_tier(fit: FitVerdict) -> SpeedTier:
    """Classify a verdict once, for every caller that used to classify it
    itself."""
    if fit.state is FitState.TOO_BIG:
        return SpeedTier.TOO_BIG
    if fit.state is not FitState.PARTIAL:
        return SpeedTier.FULL
    if fit.offload_fraction <= _LIGHT_SPILL_CEILING:
        return SpeedTier.LIGHT_SPILL
    if fit.offload_fraction < _MODERATE_SPILL_CEILING:
        return SpeedTier.MODERATE_SPILL
    return SpeedTier.HEAVY_SPILL


# The tiers a build may be starred at. Anything `copy.py` would describe with
# spill wording heavier than "most of it still fits" is excluded, by
# construction rather than by a second, independently tuned number: the
# recommendation policy no longer has a threshold of its own to drift out of
# step with the badge's.
RECOMMENDABLE_TIERS = frozenset({SpeedTier.FULL, SpeedTier.LIGHT_SPILL})

# The window the agent runs at, the agent gate's `WINDOW_FLOOR`: a star that
# carries the agent is a build the load plan keeps resident at this window.
AGENT_WINDOW = CONTEXT_RUNGS[-1]

# Without a graphics card the processor reads every weight for every token, and
# reading a grounded turn's prompt comes first: on a Ryzen 7 5800X even 1.7B and
# 2B models waited 86 s or more for their first word of the agent's 9,500-token
# opening, 22 Nov 2026 (docs/adr/0094-the-star-goes-to-a-model-that-runs-the-agent.md).
# So only a small build is starred there, for Basic chat: about Qwen3 4B at
# UD-Q4_K_XL. Integrated graphics count as the processor (`selection.py`).
PROCESSOR_STAR_CEILING_BYTES = 3 * 1024**3


def quick_here(footprint_bytes: int, budget: HardwareBudget) -> bool:
    """Whether a build may be starred for its speed here: any build on a graphics
    card or Apple's unified memory, only a small one on the processor alone."""
    return budget.has_gpu or footprint_bytes <= PROCESSOR_STAR_CEILING_BYTES
