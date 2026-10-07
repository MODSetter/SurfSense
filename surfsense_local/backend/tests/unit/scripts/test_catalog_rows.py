"""The OpenRouter screening sweep becomes rows of the shipped list, beside the ones it has."""

import shutil
from datetime import date
from pathlib import Path

import catalog_rows
import pytest
from capability_list import shipped as shipped_list
from capability_list.ladder_input import LadderResults
from capability_list.merge import merged
from capability_list.rows import COMMITTED_INPUT, measured_rows, with_ladder_rows
from capability_list.sweep_input import SweepResults
from capability_list.sweep_rows import sweep_rows

from modules.llm.capability.measured.loader import SHIPPED
from modules.llm.capability.measured.schema import CapabilityList, MeasuredModel

pytestmark = pytest.mark.unit

SAMPLE = Path(__file__).resolve().parents[2] / "fixtures" / "sweep_results_sample.json"


def _sweep() -> SweepResults:
    return SweepResults.model_validate_json(SAMPLE.read_text(encoding="utf-8"))


def _rows() -> dict[str, MeasuredModel]:
    """The sweep's rows by key; a key both screened and assumed is the screened one."""
    rows: dict[str, MeasuredModel] = {}
    for row in sweep_rows(_sweep(), date(2026, 1, 1)):
        rows.setdefault(row.key, row)
    return rows


def _shipped() -> CapabilityList:
    return CapabilityList.model_validate_json(SHIPPED.read_text(encoding="utf-8"))


def test_passing_both_cases_is_tested_at_the_agent_level() -> None:
    """The bar is both cases: PDF brief and Board pack."""
    row = _rows()["gpt-5-2"]

    assert row.level == "agent"
    assert (row.suite, row.suite_version) == ("openrouter-screen", 1)
    assert row.passes.model_dump() == {"passed": 2, "counted": 2, "run": 2}
    assert row.match.served == ["remote"]
    assert (row.provider, row.host, row.model_id) == (
        "openrouter",
        "openrouter.ai",
        "openai/gpt-5.2",
    )
    assert row.measured_on == date(2026, 10, 7)


def test_passing_one_case_is_below_the_bar_with_its_counts() -> None:
    """The counts go with it, so the switch can say "Passed 1 of 2"."""
    row = _rows()["mistral-small-3-2-24b-instruct"]

    assert row.level == "studio_only"
    assert row.passes.model_dump() == {"passed": 1, "counted": 2, "run": 2}
    # A failure holds on a copy of one's own, as the ladder's do.
    assert row.match.served == ["remote", "local"]
    assert row.note.startswith("Passed 1 of 2 screening cases")


def test_failing_the_smoke_check_runs_neither_case() -> None:
    """Nothing ran, and the note says why rather than echoing the sweep's notes."""
    row = _rows()["llama-4-scout"]

    assert row.level == "studio_only"
    assert row.passes.model_dump() == {"passed": 0, "counted": 2, "run": 0}
    assert "smoke check" in row.note


def test_an_expensive_flagship_is_assumed_to_pass_without_runs() -> None:
    """Marked by its suite, with no counts behind it."""
    row = _rows()["claude-opus-4-6"]

    assert row.level == "agent"
    assert row.assumed is True
    assert row.passes.model_dump() == {"passed": 0, "counted": 0, "run": 0}
    assert row.note == "Not run: an expensive flagship assumed to pass"


def test_the_date_given_is_used_when_the_results_name_none() -> None:
    """The sweep's own date wins when it has one."""
    undated = _sweep().model_copy(update={"measured_on": None})

    rows = sweep_rows(undated, date(2026, 10, 9))

    assert {row.measured_on for row in rows} == {date(2026, 10, 9)}


def test_the_list_s_own_rows_win_over_the_sweep() -> None:
    """The ladder's 8-case rows stand, by exact key or by a server's spelling."""
    written, left_out = merged(_shipped(), sweep_rows(_sweep(), date(2026, 1, 1)))
    by_key = {row.key: row for row in written.models}

    assert by_key["qwen3-8-27b"].suite == "create-and-edit"
    assert by_key["qwen3-8-27b"].passes.passed == 8
    assert "gemma-4-31b" not in by_key
    # Screened and assumed: the screening, which was run, stands.
    assert by_key["gpt-5-2"].suite == "openrouter-screen"
    assert {(row.key, row.suite) for row in left_out} == {
        ("qwen3-8-27b", "openrouter-screen"),
        ("gemma-4-31b", "openrouter-screen"),
        ("gpt-5-2", "assumed"),
    }
    assert len(written.models) == len(_shipped().models) + 4


def test_the_script_writes_a_list_the_app_loads_and_the_ladder_keeps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rewriting the ladder's rows afterwards leaves the sweep's in place."""
    copy = tmp_path / "capabilities.json"
    shutil.copy(SHIPPED, copy)
    monkeypatch.setattr(shipped_list, "SHIPPED", copy)

    catalog_rows.main([str(SAMPLE), "--date", "2026-10-07"])

    written = CapabilityList.model_validate_json(copy.read_text(encoding="utf-8"))
    ladder = measured_rows(
        LadderResults.model_validate_json(COMMITTED_INPUT.read_text(encoding="utf-8"))
    )
    assert len(written.models) == len(_shipped().models) + 4
    assert with_ladder_rows(written, ladder) == written
    assert copy.read_text(encoding="utf-8").endswith("}\n")
