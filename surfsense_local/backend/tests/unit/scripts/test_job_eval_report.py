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
