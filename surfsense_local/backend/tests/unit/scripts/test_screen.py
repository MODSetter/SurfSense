"""The committed screen, folded at the JSON level so its provenance extras survive."""

import json
from pathlib import Path

import pytest
from capability_list.screen import folded_screen, write_screen

pytestmark = pytest.mark.unit

SWEEP = (
    Path(__file__).resolve().parents[3]
    / "scripts"
    / "capability_list"
    / "sweep"
)


def _model(key: str, **over) -> dict:
    entry = {
        "id": f"openai/{key}",
        "key": key,
        "reads_images": False,
        "status": "done",
        "level": "agent",
        "passed": 2,
        "counted": 2,
        "run": 2,
    }
    entry.update(over)
    return entry


def test_folding_the_rerun_into_the_first_screen_rebuilds_the_committed_one(
    tmp_path: Path,
) -> None:
    """The 8 October re-run folded into the 7 October screen, byte for byte.

    The committed screen was built by hand; the command's fold must land
    on exactly it, extras, ordering and all.
    """
    base = json.loads(
        (SWEEP / "runs" / "2026-10-07-screen" / "sweep-results.json").read_text(
            encoding="utf-8"
        )
    )
    rerun = json.loads(
        (SWEEP / "runs" / "2026-10-08-zero-ids" / "sweep-results.json").read_text(
            encoding="utf-8"
        )
    )
    out = tmp_path / "openrouter-screen-v1.json"

    write_screen(folded_screen(base, rerun), out)

    assert out.read_bytes() == (SWEEP / "openrouter-screen-v1.json").read_bytes()


def test_the_fold_moves_entries_whole_extras_and_all() -> None:
    """A re-run's row replaces the first one entire, not field by field."""
    base = {
        "generated": "2026-10-07T00:00:00+00:00",
        "models": [_model("gpt-6-luna", passed=0, runs=["run-a"], served_by=["x"])],
        "unfinished": [],
        "assumed": [],
    }
    rerun = {
        "models": [_model("gpt-6-luna", passed=2, runs=["run-b"], served_by=["y"])],
        "unfinished": [],
        "assumed": [],
    }

    folded = folded_screen(base, rerun)

    assert folded["models"] == rerun["models"]
    assert folded["generated"] == "2026-10-07T00:00:00+00:00"


def test_the_fold_sums_what_the_two_runs_spent() -> None:
    """The committed screen's `spent` is both runs' spend, not the latest."""
    base = {"spent": 60.7301, "models": [], "unfinished": [], "assumed": []}
    rerun = {"spent": 4.6823, "models": [], "unfinished": [], "assumed": []}

    assert folded_screen(base, rerun)["spent"] == pytest.approx(65.4124)


def test_a_model_the_rerun_left_unfinished_drops_out() -> None:
    """No verdict in the re-run: the first measurement does not survive it."""
    base = {"models": [_model("mimo-v2-6-pro")], "unfinished": [], "assumed": []}
    rerun = {
        "models": [],
        "unfinished": [
            _model(
                "mimo-v2-6-pro",
                status="running",
                level=None,
                passed=None,
                counted=None,
                run=None,
            )
        ],
        "assumed": [],
    }

    folded = folded_screen(base, rerun)

    assert folded["models"] == []
    assert [entry["key"] for entry in folded["unfinished"]] == ["mimo-v2-6-pro"]


def test_a_capped_model_in_the_reruns_assumed_list_is_the_reruns_verdict() -> None:
    """The re-run's capped row joins `assumed` whole, extras and all."""
    capped = {
        "id": "openai/gpt-6-luna",
        "key": "gpt-6-luna",
        "reads_images": False,
        "level": "agent",
        "assumed": True,
        "prices_per_million": {"input": 5.0},
    }
    base = {"models": [_model("gpt-6-luna")], "unfinished": [], "assumed": []}
    rerun = {"models": [], "unfinished": [], "assumed": [capped]}

    folded = folded_screen(base, rerun)

    assert folded["models"] == []
    assert folded["assumed"] == [capped]
