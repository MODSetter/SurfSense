"""The bar a model's column is held to, and the level it earns."""

from dataclasses import dataclass

from capability_list.ladder_input import Case, ModelResults
from modules.llm.capability import Level

# The maintainer's bar for the agent.
AGENT_BAR = 0.8
# Near the bar: Haiku 4.5's 5 of 8, all failures a skipped look at its pages.
NEAR_BAR = 0.6
# Either one means the agent cannot be left to work: nothing made, or no end.
DISQUALIFYING = frozenset({"made_no_document", "looped"})


@dataclass(frozen=True)
class Verdict:
    level: Level
    passed: int
    counted: int
    run: int


def verdict(model: ModelResults, cases: dict[str, Case]) -> Verdict:
    counted = [
        name
        for name, outcome in model.cases.items()
        if outcome != "n/a" and (model.reads_images or not cases[name].image_only)
    ]
    passed = sum(1 for name in counted if model.cases[name] == "pass")
    run = sum(1 for o in model.cases.values() if o not in ("n/a", "not_run"))
    rate = passed / len(counted) if counted else 0.0
    required = all(
        model.cases[name] == "pass" for name, case in cases.items() if case.required
    )
    eligible = required and not (model.failures() & DISQUALIFYING)
    if eligible and rate >= AGENT_BAR:
        level = Level.AGENT
    elif eligible and rate >= NEAR_BAR:
        level = Level.AGENT_LIMITED
    else:
        level = Level.STUDIO_ONLY
    return Verdict(level, passed, len(counted), run)
