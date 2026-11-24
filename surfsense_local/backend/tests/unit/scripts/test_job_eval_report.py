"""The job eval's roll-up keeps apart runs that differ in their checker or their firm settings."""

import json
from pathlib import Path

import pytest
from job_eval.report import report

pytestmark = pytest.mark.unit


def _record(folder: Path, name: str, **changes: object) -> None:
    record = {
        "case": "ncsc-wisp",
        "model": "openrouter:qwen/qwen3.8-27b",
        "checker": None,
        "started": name,
        "gold_status": "model-checked",
        "settings": {"job": {"provider_na": False}},
        "scored_rows": 10,
        "correct": 7,
        "false_yes": 0,
        "yes_without_quote": 0,
        "dropdown_violations": 0,
        "integrity": [],
        "misses": {},
        "suggested_right": 0,
        "suggested_wrong": 0,
        "provider_setting_flipped": {"provider_on": True, "correct": 8},
        "spend": {"dollars": 0.01},
        "seconds": 30.0,
        **changes,
    }
    (folder / name).mkdir()
    (folder / name / "run.json").write_text(json.dumps(record), encoding="utf-8")


def test_runs_with_another_setting_or_checker_get_their_own_line(tmp_path):
    """Pooled together, runs with the setting on and off would average two different jobs."""
    _record(tmp_path, "a")
    _record(
        tmp_path,
        "b",
        settings={"job": {"provider_na": True}},
        provider_setting_flipped={"provider_on": False, "correct": 6},
    )
    _record(tmp_path, "c", checker="openrouter:google/gemma-4-31b-it")

    rows = [line for line in report(tmp_path).splitlines() if "ncsc-wisp |" in line]

    assert len(rows) == 3
    assert any("with provider_na on" in row and "60.0% (off)" in row for row in rows)
    assert any("checked by openrouter:google/gemma-4-31b-it" in row for row in rows)


def test_runs_at_another_reasoning_get_their_own_line(tmp_path):
    """A run at low effort answers differently from one with reasoning off: never one line."""
    _record(tmp_path, "a", settings={"reasoning": "off", "job": {}})
    _record(tmp_path, "b", settings={"reasoning": "low", "job": {}})

    rows = [line for line in report(tmp_path).splitlines() if "ncsc-wisp |" in line]

    assert len(rows) == 2 and any("reasoning low" in row for row in rows)


def test_a_case_with_no_scored_rows_has_no_accuracy(tmp_path):
    """A gold file with no rows scores none: its line says "—" for both accuracies, and the
    report still gives every other case's line."""
    _record(tmp_path, "a")
    _record(
        tmp_path,
        "e",
        case="empty",
        scored_rows=0,
        correct=0,
        provider_setting_flipped={"provider_on": True, "correct": 0},
    )

    lines = report(tmp_path).splitlines()
    [empty] = [line for line in lines if line.startswith("| empty |")]
    [ordinary] = [line for line in lines if line.startswith("| ncsc-wisp |")]

    # Correct per run, accuracy, and accuracy with the provider setting flipped.
    assert _cells(empty)[3:6] == ["0/0", "—", "—"]
    assert _cells(ordinary)[3:6] == ["7/10", "70.0%", "80.0% (on)"]


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.split("|")[1:-1]]
