"""Badge wording.

A badge is a **verdict plus one plain line of why**. The verdict is what someone
choosing a model needs (fast, slower, or impossible); the mechanism is the
explanation, not the headline.

Wording branches on two facts the budget already carries, `uma` and `has_gpu`,
and never on the runtime's name. One label set is wrong on two of the three
targets.

**No em dashes and no hyphens in anything here.** Commas, full stops or
parentheses. That is a standing rule for every user facing string in this phase.
"""

from dataclasses import dataclass

from modules.llm.fit.budget import HardwareBudget
from modules.llm.fit.estimate import FitVerdict
from modules.llm.fit.states import FitState

# Above this the spill is no longer something a user can ignore. Below it, most
# of the model is still resident and the difference is barely noticeable.
_NOTICEABLE_SPILL = 0.35


@dataclass(frozen=True)
class Badge:
    verdict: str
    reason: str


def badge(fit: FitVerdict, budget: HardwareBudget) -> Badge:
    if fit.state is FitState.TOO_BIG:
        return Badge("Won't fit", _refusal(fit, budget))
    if fit.state is FitState.PARTIAL:
        return Badge("Reduced speed", _spill(fit, budget))
    if not budget.has_gpu:
        return Badge("Works here", "Runs on your processor")
    return Badge(
        "Full speed",
        "Runs entirely on the GPU" if budget.uma else "Runs entirely on your graphics card",
    )


def _spill(fit: FitVerdict, budget: HardwareBudget) -> str:
    where = "the GPU" if budget.uma else "the graphics card"
    if fit.offload_fraction <= _NOTICEABLE_SPILL:
        return f"A little too big for {where}. Most of it still fits."
    return f"Well over {where}'s memory. Expect it to be slow."


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
