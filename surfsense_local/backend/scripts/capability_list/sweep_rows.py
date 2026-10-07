"""The capability list's rows from the OpenRouter screening sweep."""

from datetime import date

from capability_list.sweep_input import AssumedModel, SweepResults, SweptModel
from modules.llm.capability import model_key
from modules.llm.capability.measured.schema import (
    ASSUMED_NOTE,
    ASSUMED_SUITE,
    SCREEN_SUITE,
    Match,
    MeasuredModel,
    Passes,
)

SUITE_VERSION = 1
# Both cases must pass: a PDF brief and a board pack, after the smoke check.
SCREEN_BAR = 2
PROVIDER = "openrouter"
HOST = "openrouter.ai"


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
    return (
        f"Passed {model.passed} of {model.counted} screening cases on OpenRouter: "
        "a PDF brief and a board pack."
    )
