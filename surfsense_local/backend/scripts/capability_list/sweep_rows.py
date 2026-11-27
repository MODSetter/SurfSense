"""The capability list's rows from a screening sweep: on OpenRouter, or the same
two cases run on this computer's llama.cpp for a model no provider serves."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from capability_list.merge import LeftOut, merged, same_model
from capability_list.sweep_input import AssumedModel, SweepResults, SweptModel
from modules.llm.capability import model_key
from modules.llm.capability.measured.schema import (
    ASSUMED_NOTE,
    ASSUMED_SUITE,
    LOCAL_SCREEN_SUITE,
    SCREEN_SUITE,
    CapabilityList,
    Match,
    MeasuredModel,
    Passes,
    Served,
)

COMMITTED_SCREEN = Path(__file__).with_name("sweep") / "openrouter-screen-v1.json"

SUITE_VERSION = 1
# Both cases must pass: a PDF brief and a board pack, after the smoke check.
SCREEN_BAR = 2
# How the sweep notes a case stopped at its per-case dollar cap (tests/live/sweep/attempt.py).
CASE_CAP = "spent past the per-case dollar cap"


@dataclass(frozen=True)
class Place:
    """Where a screening ran, and so where its rows hold."""

    suite: str
    provider: str
    host: str
    # A pass holds where it was run.
    served_pass: tuple[Served, ...]
    # A provider's failure holds everywhere, since a copy of one's own is the same
    # model or a smaller one; a failure here says nothing of the full-size model.
    served_fail: tuple[Served, ...]
    words: str


OPENROUTER = Place(
    SCREEN_SUITE,
    "openrouter",
    "openrouter.ai",
    ("remote",),
    ("remote", "local"),
    "on OpenRouter",
)
THIS_COMPUTER = Place(
    LOCAL_SCREEN_SUITE,
    "llamacpp",
    "localhost",
    ("local",),
    ("local",),
    "on this computer's llama.cpp",
)
PROVIDER = OPENROUTER.provider
HOST = OPENROUTER.host


def sweep_rows(
    sweep: SweepResults, measured_on: date, place: Place = OPENROUTER
) -> list[MeasuredModel]:
    """Screened rows first, so a model both screened and assumed keeps its counts.

    Only models the sweep has a verdict for; each dated by its own runs, else
    by the sweep's date, else by `measured_on`.
    """
    when = sweep.measured_on or measured_on
    return [
        *(
            _screened(model, model.measured_on or when, place)
            for model in sweep.measured()
        ),
        *(_assumed(model, when) for model in sweep.assumed),
    ]


def with_screen_rows(
    shipped: CapabilityList, screen: list[MeasuredModel]
) -> tuple[CapabilityList, list[LeftOut]]:
    """The screen's rows in place of its suites', then every other row they do not name.

    Rewriting from sweep results keeps the ladder's rows, and a suite the
    screen does not cover keeps its place. The screen is the
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
    # `merged` appends the screen's rows after the kept ones, so a suite the
    # screen does not cover — local-screen — would move ahead of them. The
    # screen's rows take the shipped screen block's place instead, and every
    # other row keeps its place around them.
    block = [
        index
        for index, row in enumerate(shipped.models)
        if row.suite in {SCREEN_SUITE, ASSUMED_SUITE}
    ]
    cut = block[0] if block else len(shipped.models)
    at = {row.key: index for index, row in enumerate(shipped.models)}
    screen_rows = [
        row for row in written.models if row.suite in {SCREEN_SUITE, ASSUMED_SUITE}
    ]
    kept = [
        row for row in written.models if row.suite not in {SCREEN_SUITE, ASSUMED_SUITE}
    ]
    written = written.model_copy(
        update={
            "models": [
                *[row for row in kept if at[row.key] < cut],
                *screen_rows,
                *[row for row in kept if at[row.key] >= cut],
            ]
        }
    )
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


def _screened(
    model: SweptModel, measured_on: date, place: Place = OPENROUTER
) -> MeasuredModel:
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
        match=Match(
            keys=[key],
            served=list(place.served_pass if passed else place.served_fail),
        ),
        level="agent" if passed else "studio_only",
        suite=place.suite,
        suite_version=SUITE_VERSION,
        measured_on=measured_on,
        provider=place.provider,
        host=place.host,
        model_id=model.id,
        reads_images=model.reads_images,
        passes=Passes(passed=model.passed, counted=model.counted, run=model.run),
        note=_note(model, place),
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


def _note(model: SweptModel, place: Place = OPENROUTER) -> str:
    """English, shown as written: the sweep's own notes are its record, not the user's."""
    if model.run == 0:
        return "Did not pass the smoke check, so neither screening case ran."
    if model.passed >= SCREEN_BAR:
        return (
            f"Passed both screening cases {place.words}: a PDF brief and a board pack."
        )
    said = (
        f"Passed {model.passed} of {model.counted} screening cases {place.words}: "
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
