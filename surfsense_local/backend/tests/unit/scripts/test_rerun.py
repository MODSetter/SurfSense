"""A re-run's results fold into a screen the way the committed one was built by hand."""

from datetime import date

import pytest
from capability_list.rerun import folded
from capability_list.sweep_input import SweepResults, SweptModel

pytestmark = pytest.mark.unit


def _swept(key: str, **over) -> SweptModel:
    fields = {
        "id": f"openai/{key}",
        "key": key,
        "reads_images": False,
        "status": "done",
        "level": "agent",
        "passed": 2,
        "counted": 2,
        "run": 2,
    }
    fields.update(over)
    return SweptModel(**fields)


def _screen(*models: SweptModel) -> SweepResults:
    return SweepResults(models=list(models))


def test_a_reruns_verdict_replaces_the_first_one() -> None:
    """The id-0 fix re-measured 18 models; the screen keeps the new verdicts."""
    base = _screen(_swept("gpt-6-luna", passed=0, counted=2, level="below", run=1))
    rerun = _screen(_swept("gpt-6-luna", passed=2, counted=2, level="agent", run=2))

    folded_models = {model.key: model for model in folded(base, rerun).models}

    assert folded_models["gpt-6-luna"].passed == 2
    assert folded_models["gpt-6-luna"].run == 2


def test_a_model_the_rerun_left_unfinished_drops_out() -> None:
    """The re-run invalidates the first measurement, so no row survives it."""
    base = _screen(_swept("mimo-v2-6-pro-ultraspeed"))
    rerun = _screen(
        _swept(
            "mimo-v2-6-pro-ultraspeed",
            status="unresolved",
            level=None,
            passed=None,
            counted=None,
            run=None,
        )
    )

    assert [model.key for model in folded(base, rerun).models] == []


def test_a_capped_model_in_the_reruns_assumed_list_is_the_reruns_verdict() -> None:
    """The sweep writes a capped model to `assumed`, not `unfinished`.

    The fixture is the sweep's own `_capped_row` shape (level agent,
    assumed True) — the shape `results.write()` produces: capped rows are
    `done`, so they never appear in `unfinished`.
    """
    from capability_list.sweep_input import AssumedModel

    base = _screen(_swept("gpt-6-luna"))
    rerun = SweepResults(
        assumed=[
            AssumedModel(id="openai/gpt-6-luna", key="gpt-6-luna", reads_images=False)
        ],
    )

    result = folded(base, rerun)

    assert [model.key for model in result.models] == []
    assert [model.key for model in result.assumed] == ["gpt-6-luna"]
    assert [model.key for model in result.unfinished] == []


def test_a_measured_rerun_verdict_clears_a_stale_base_assumption() -> None:
    """A re-run that measures a model the base assumed leaves no stale row.

    The base's assumed entry must go: the folded screen holds the measured
    verdict, not the assumption beside it.
    """
    from capability_list.sweep_input import AssumedModel

    base = SweepResults(
        assumed=[
            AssumedModel(id="openai/gpt-6-luna", key="gpt-6-luna", reads_images=False)
        ]
    )
    rerun = _screen(_swept("gpt-6-luna", passed=2, counted=2, level="agent"))

    result = folded(base, rerun)

    assert [model.key for model in result.models] == ["gpt-6-luna"]
    assert [model.key for model in result.assumed] == []


def test_a_model_the_rerun_measured_leaves_the_unfinished_list() -> None:
    """The folded screen's unfinished list names only models still unmeasured."""
    base = SweepResults(
        unfinished=[
            _swept(
                "gpt-6-luna",
                status="running",
                level=None,
                passed=None,
                counted=None,
                run=None,
            )
        ]
    )
    rerun = _screen(_swept("gpt-6-luna"))

    result = folded(base, rerun)

    assert [model.key for model in result.models] == ["gpt-6-luna"]
    assert [model.key for model in result.unfinished] == []


def test_the_folded_screen_is_dated_by_the_rerun() -> None:
    """The fold is the newer measurement; without a re-run date it keeps the base's."""
    base = SweepResults(measured_on=date(2026, 10, 7))
    rerun = SweepResults(measured_on=date(2026, 10, 8))

    assert folded(base, rerun).measured_on == date(2026, 10, 8)
    assert folded(base, SweepResults()).measured_on == date(2026, 10, 7)


def test_a_model_the_rerun_left_unfinished_drops_its_assumption() -> None:
    """A re-run that never measured an assumed model leaves no stale row.

    The base assumed it; the re-run left it unfinished, so the folded
    screen holds neither the assumption nor a measurement.
    """
    from capability_list.sweep_input import AssumedModel

    base = SweepResults(
        assumed=[
            AssumedModel(id="openai/gpt-6-luna", key="gpt-6-luna", reads_images=False)
        ]
    )
    rerun = SweepResults(
        unfinished=[
            _swept(
                "gpt-6-luna",
                status="running",
                level=None,
                passed=None,
                counted=None,
                run=None,
            )
        ]
    )

    result = folded(base, rerun)

    assert [model.key for model in result.models] == []
    assert [model.key for model in result.assumed] == []
    assert [model.key for model in result.unfinished] == ["gpt-6-luna"]


def test_a_model_unfinished_in_the_rerun_list_drops_out() -> None:
    """Unfinished entries name models too, and the same invalidation applies."""
    base = _screen(_swept("mimo-v2-6-pro-ultraspeed"))
    rerun = SweepResults(
        unfinished=[
            _swept(
                "mimo-v2-6-pro-ultraspeed",
                status="running",
                level=None,
                passed=None,
                counted=None,
                run=None,
            )
        ]
    )

    assert [model.key for model in folded(base, rerun).models] == []
