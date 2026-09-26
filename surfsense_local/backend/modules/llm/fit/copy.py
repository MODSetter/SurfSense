"""Badge wording.

A badge is a **warning**, shown only when there is something to warn about. A
build that runs fully says nothing, and neither does one that spills a little:
that tier is recommended on purpose, and a warning beside the star would
contradict it. So the tiers a build can be recommended at carry no badge, by
construction rather than by coincidence.

Where a badge shows, it is a verdict plus one plain line of why. The verdict is
what someone choosing a model needs; the mechanism is the explanation. Wording
branches on `uma`, which the budget carries, and never on the runtime's name.

Which band a verdict falls in is `speed.speed_tier`'s job, not this module's, so
the badge and the recommendation read one classification.

**No em dashes and no hyphens in anything here.** Commas, full stops or
parentheses. That is a standing rule for every user facing string.
"""

from dataclasses import dataclass
from enum import StrEnum

from modules.llm.fit.budget import HardwareBudget
from modules.llm.fit.estimate import FitVerdict
from modules.llm.fit.speed import SpeedTier, speed_tier


class BadgeLevel(StrEnum):
    """How loudly a build is flagged: not at all, a notice, or a refusal."""

    NONE = "none"
    NOTICE = "notice"
    REFUSE = "refuse"


@dataclass(frozen=True)
class Badge:
    level: BadgeLevel
    # Empty when the level is NONE: there is nothing to name.
    verdict: str
    # Empty when there is nothing to explain.
    reason: str


def badge(fit: FitVerdict, budget: HardwareBudget) -> Badge:
    where = "the GPU" if budget.uma else "the graphics card"
    elsewhere = "the CPU" if budget.uma else "the processor"
    tier = speed_tier(fit)
    if tier is SpeedTier.TOO_BIG:
        return Badge(BadgeLevel.REFUSE, "Won't fit", _refusal(fit, budget))
    if tier is SpeedTier.HEAVY_SPILL:
        return Badge(
            BadgeLevel.NOTICE,
            "Reduced speed",
            f"Well over {where}'s memory. Expect it to be slow.",
        )
    if tier is SpeedTier.MODERATE_SPILL:
        return Badge(
            BadgeLevel.NOTICE,
            "Reduced speed",
            f"Too big for {where}, so part runs on {elsewhere}.",
        )
    if tier is SpeedTier.LIGHT_SPILL:
        return Badge(BadgeLevel.NONE, "", f"Most of it runs on {where}.")
    return Badge(BadgeLevel.NONE, "", "")


def _refusal(fit: FitVerdict, budget: HardwareBudget) -> str:
    machine = "This Mac" if budget.uma else "This PC"
    return f"Needs about {_gb(fit.need_bytes)}. {machine} has {_gb(fit.budget_bytes)}"


def _gb(value: int) -> str:
    """Decimal GB, as storage and download sizes are quoted everywhere else.

    One decimal, with a trailing zero dropped, so a pair reads "21 GB" and
    "13.6 GB" rather than "21.0 GB" and "14 GB". Rounding the second to a whole
    number loses the half gigabyte that decided the answer.
    """
    size = round(value / 1000**3, 1)
    return f"{size:g} GB"
