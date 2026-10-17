"""The capability list's rows from the OpenRouter screening sweep."""

from datetime import date
from pathlib import Path

from capability_list.merge import LeftOut, merged, same_model
from capability_list.sweep_input import AssumedModel, SweepResults, SweptModel
from modules.llm.capability import model_key
from modules.llm.capability.measured.schema import (
    ASSUMED_NOTE,
    ASSUMED_SUITE,
    SCREEN_SUITE,
    CapabilityList,
    Match,
    MeasuredModel,
    Passes,
)

COMMITTED_SCREEN = Path(__file__).with_name("sweep") / "openrouter-screen-v1.json"

SUITE_VERSION = 1
# Both cases must pass: a PDF brief and a board pack, after the smoke check.
SCREEN_BAR = 2
PROVIDER = "openrouter"
HOST = "openrouter.ai"
# How the sweep notes a case stopped at its per-case dollar cap (tests/live/sweep/attempt.py).
CASE_CAP = "spent past the per-case dollar cap"


def sweep_rows(sweep: SweepResults, measured_on: date) -> list[MeasuredModel]:
    """Screened rows first, so a model both screened and assumed keeps its counts.

    Only models the sweep has a verdict for; each dated by its own runs, else
    by the sweep's date, else by `measured_on`.
    """
    when = sweep.measured_on or measured_on
    return [
        *(_screened(model, model.measured_on or when) for model in sweep.measured()),
        *(_assumed(model, when) for model in sweep.assumed),
    ]


def with_screen_rows(
    shipped: CapabilityList, screen: list[MeasuredModel]
) -> tuple[CapabilityList, list[LeftOut]]:
    """The screen's rows in place of its suites', then every other row they do not name.

    Rewriting from sweep results keeps the ladder's rows. The screen is the
    source of truth for its suites: a listed screening or assumed row gives
    way to the screen's row for the same model, the way a listed ladder row
    gives way to `with_ladder_rows`. The left-out rows are the screen's rows
    a ladder row or another screen row names over, plus the shipped rows the
    screen replaces — the script prints them, the pin test ignores them.
    """
    others = [
        row
        for row in shipped.models
        if row.suite not in {SCREEN_SUITE, ASSUMED_SUITE}
    ]
    written, left_out = merged(shipped.model_copy(update={"models": others}), screen)
    for old in (
        row for row in shipped.models if row.suite in {SCREEN_SUITE, ASSUMED_SUITE}
    ):
        # A written row of a screen suite came from the screen: `merged`
        # re-validates, so identity with the screen's rows does not hold.
        new = next(
            (
                row
                for row in written.models
                if row.suite in {SCREEN_SUITE, ASSUMED_SUITE}
                and same_model(old, row)
            ),
            None,
        )
        if new is not None and new != old:
            left_out.append(LeftOut(old, new, listed=False, replaced=True))
    return written, left_out


def _screened(model: SweptModel, measured_on: date) -> MeasuredModel:
    key = _key(model.key)
    # `measured()` leaves only models with every count.
    assert model.passed is not None and model.counted is not None
    passed = model.passed >= SCREEN_BAR
    if model.level is not None and (model.level == "agent") != passed:
        raise ValueError(
            f"{model.id}: the sweep says {model.level} for {model.passed} of "
            f"{model.counted} cases"
        )
    return MeasuredModel(
        key=key,
        # A pass holds where it was run; a failure everywhere, as the ladder's rows.
        match=Match(keys=[key], served=["remote"] if passed else ["remote", "local"]),
        level="agent" if passed else "studio_only",
        suite=SCREEN_SUITE,
        suite_version=SUITE_VERSION,
        measured_on=measured_on,
        provider=PROVIDER,
        host=HOST,
        model_id=model.id,
        reads_images=model.reads_images,
        passes=Passes(passed=model.passed, counted=model.counted, run=model.run),
        note=_note(model),
    )


def _assumed(model: AssumedModel, measured_on: date) -> MeasuredModel:
    key = _key(model.key)
    return MeasuredModel(
        key=key,
        match=Match(keys=[key], served=["remote"]),
        level="agent",
        suite=ASSUMED_SUITE,
        suite_version=SUITE_VERSION,
        measured_on=measured_on,
        provider=PROVIDER,
        host=HOST,
        model_id=model.id,
        reads_images=model.reads_images,
        passes=Passes(passed=0, counted=0, run=0),
        note=ASSUMED_NOTE,
    )


def _key(key: str) -> str:
    canonical = model_key(key)
    if canonical is None:
        raise ValueError(f"{key} is an alias, not a model to list")
    return canonical


def _note(model: SweptModel) -> str:
    """English, shown as written: the sweep's own notes are its record, not the user's."""
    if model.run == 0:
        return "Did not pass the smoke check, so neither screening case ran."
    if model.passed >= SCREEN_BAR:
        return (
            "Passed both screening cases on OpenRouter: a PDF brief and a board pack."
        )
    said = (
        f"Passed {model.passed} of {model.counted} screening cases on OpenRouter: "
        "a PDF brief and a board pack."
    )
    # Counted as failed, though the model was stopped rather than wrong.
    capped = sum(CASE_CAP in note for note in _notes(model))
    if capped:
        said += f" {capped} of them stopped at the per-case dollar cap, unfinished."
    return said


def _notes(model: SweptModel) -> list[str]:
    if model.notes is None:
        return []
    return [model.notes] if isinstance(model.notes, str) else model.notes
