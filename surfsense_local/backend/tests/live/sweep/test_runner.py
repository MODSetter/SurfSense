"""The sweep's loop, driven by a stand-in case: lanes, retries, the re-run, the budget, the time limit, resume and its files."""

import json
import os
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.live.sweep import plan as plan_module
from tests.live.sweep import report
from tests.live.sweep.attempt import Attempt
from tests.live.sweep.attempt_log import AttemptLog
from tests.live.sweep.budget import Budget
from tests.live.sweep.model_list import ListedModel
from tests.live.sweep.ram_guard import RamGuard
from tests.live.sweep.runner import HARNESS_STREAK, Runner, Sweep
from tests.live.sweep.runner_lock import SweepBusyError

pytestmark = pytest.mark.unit

STAND_IN = Path(__file__).parent / "stand_in_case.py"
BACKEND = Path(__file__).resolve().parents[3]
PLENTY = 64 << 30


def _model(model_id: str, prompt: float = 0.1) -> ListedModel:
    return ListedModel(model_id, model_id.split("/")[-1], prompt, 0.0, 131_072, False)


GOOD, WEAK, SPLIT = _model("a/good"), _model("a/weak"), _model("a/split")
FLAGSHIP = _model("big/flagship", prompt=5.0)


@pytest.fixture(autouse=True)
def no_pause_between_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retries start at once in these tests."""
    monkeypatch.setattr(plan_module, "RETRY_AFTER_SECONDS", 0.0)


def _sweep(tmp_path: Path, plan: dict, models: list[ListedModel], **changes) -> Sweep:
    (tmp_path / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    settings = {
        "out": tmp_path / "sweep",
        "models": models,
        "assumed": [FLAGSHIP],
        "listing": {"file": "listing.json"},
        "command_for": lambda case, lane_dir: [sys.executable, str(STAND_IN), case],
        "child_env": {
            "STAND_IN_PLAN": str(tmp_path / "plan.json"),
            "STAND_IN_TRACE": str(tmp_path / "trace"),
            "SYSTEMROOT": "C:\\Windows",
        },
        "cwd": tmp_path,
        "guard": RamGuard(lanes=3),
        "budget": Budget(cap=100.0, case_cap=3.0),
        "available_bytes": lambda: PLENTY,
        "poll_seconds": 0.05,
        "say": lambda line: None,
    }
    return Sweep(**{**settings, **changes})


def _trace(tmp_path: Path) -> list[dict]:
    runs = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (tmp_path / "trace").iterdir()
    ]
    return sorted(runs, key=lambda run: run["start"])


def _results(tmp_path: Path) -> dict:
    return json.loads((tmp_path / "sweep" / "sweep-results.json").read_text("utf-8"))


def test_a_sweep_gives_each_model_its_verdict_and_writes_it_for_the_catalog(
    tmp_path: Path,
) -> None:
    """Good passes both; weak fails smoke and runs nothing else; split fails the board pack, passes it again, and counts as agent."""
    plan = {
        "a/weak|smoke": ["failed"],
        "a/split|board-pack": ["failed", "passed"],
    }

    Runner(_sweep(tmp_path, plan, [GOOD, WEAK, SPLIT])).run()

    saved = _results(tmp_path)
    rows = {row["id"]: row for row in saved["models"]}
    assert {k: rows["a/good"][k] for k in ("level", "passed", "counted", "run")} == {
        "level": "agent",
        "passed": 2,
        "counted": 2,
        "run": 2,
    }
    weak = rows["a/weak"]
    assert (weak["level"], weak["passed"], weak["counted"], weak["run"]) == (
        "below",
        0,
        2,
        0,
    )
    assert (weak["pdf_brief"], weak["board_pack"]) == ("not_run", "not_run")
    split = rows["a/split"]
    assert (split["level"], split["board_pack"], split["attempts"]) == (
        "agent",
        "pass",
        4,
    )
    assert split["served_by"] == ["Upstream"]
    assert split["cost"] == pytest.approx(0.4)
    assert saved["assumed"][0]["id"] == "big/flagship"
    assert saved["spent"] == pytest.approx(0.8)
    per_model = tmp_path / "sweep" / "a__split" / "summary.json"
    assert json.loads(per_model.read_text("utf-8"))["level"] == "agent"
    lines = AttemptLog(tmp_path / "sweep" / "attempts.jsonl").read()
    assert len(lines) == len(_trace(tmp_path)) == 8


def test_cases_run_in_parallel_lanes_each_with_its_own_ports_data_and_temp(
    tmp_path: Path,
) -> None:
    """Three lanes start together, none sharing a port block, data dir or temp dir."""
    models = [_model(f"m/{n}") for n in range(3)]
    sweep = _sweep(tmp_path, {}, models)
    sweep.child_env["STAND_IN_SECONDS"] = "1.0"

    Runner(sweep).run()

    first_wave = _trace(tmp_path)[:3]
    assert len({r["port_base"] for r in first_wave}) == 3
    assert len({r["data_dir"] for r in first_wave}) == 3
    assert len({r["temp"] for r in first_wave}) == 3
    assert {r["provider"] for r in first_wave} == {"openrouter"}
    assert max(r["start"] for r in first_wave) - min(r["start"] for r in first_wave) < 1


def test_a_transient_fault_is_retried_and_three_in_a_row_leave_the_model_unresolved(
    tmp_path: Path,
) -> None:
    """--retry-unresolved on a restart gives the case its tries back."""
    plan = {
        "a/good|pdf-brief": ["transient", "passed"],
        "a/weak|smoke": ["transient", "harness", "chat", "passed"],
    }

    Runner(_sweep(tmp_path, plan, [GOOD, WEAK])).run()

    saved = _results(tmp_path)
    rows = {row["id"]: row for row in saved["models"]}
    assert (rows["a/good"]["level"], rows["a/good"]["attempts"]) == ("agent", 4)
    # Never measured, so not a row for the catalog: it would read as a smoke failure.
    assert "a/weak" not in rows
    (weak,) = saved["unfinished"]
    assert (weak["status"], weak["smoke"]) == ("unresolved", "unresolved")

    Runner(_sweep(tmp_path, plan, [GOOD, WEAK], retry_unresolved=True)).run()

    rows = {row["id"]: row for row in _results(tmp_path)["models"]}
    assert rows["a/weak"]["level"] == "agent"
    weak = sorted(
        (r["case"], r["attempt"]) for r in _trace(tmp_path) if r["model"] == "a/weak"
    )
    assert weak == [("board-pack", 1), ("pdf-brief", 1)] + [
        ("smoke", n) for n in range(1, 5)
    ]
    assert len([r for r in _trace(tmp_path) if r["model"] == "a/good"]) == 4


def test_the_budget_counts_every_attempt_and_stops_before_a_case_that_would_pass_it(
    tmp_path: Path,
) -> None:
    """Each run charges $1 and is expected to cost $1; a $3 cap runs three, one lane at a time."""
    pricey = [_model(f"m/{n}", prompt=25.0) for n in range(4)]
    sweep = _sweep(
        tmp_path,
        {},
        pricey,
        guard=RamGuard(lanes=1),
        budget=Budget(cap=3.0, case_cap=10.0),
    )
    sweep.child_env["STAND_IN_DOLLARS"] = "1.0"

    Runner(sweep).run()

    runs = _trace(tmp_path)
    assert len(runs) == 3
    assert [float(r["stop"]) for r in runs] == [3.0, 2.0, 1.0]
    log = (tmp_path / "sweep" / "runner.log").read_text("utf-8")
    assert "budget reached" in log
    # Models it stopped short of are not rows for the catalog, which reads counts as a measurement.
    saved = _results(tmp_path)
    assert saved["models"] == []
    assert [(r["id"], r["status"], r["passed"]) for r in saved["unfinished"]] == [
        ("m/0", "running", None),
        ("m/1", "running", None),
        ("m/2", "running", None),
        ("m/3", "pending", None),
    ]
    last = max(a.ended for a in AttemptLog(sweep.out / "attempts.jsonl").read())
    assert saved["date"] == datetime.fromtimestamp(last, UTC).date().isoformat()


def test_a_case_past_its_time_limit_is_killed_and_counted_only_if_the_model_wrote(
    tmp_path: Path,
) -> None:
    """A runaway model fails the case; a provider that sent nothing is retried."""
    plan = {"a/good|smoke": ["hang"], "a/weak|smoke": ["hang-silent", "passed"]}

    Runner(_sweep(tmp_path, plan, [GOOD, WEAK], case_seconds=2.0)).run()

    lines = AttemptLog(tmp_path / "sweep" / "attempts.jsonl").read()
    smoke = {(a.model, a.number): a for a in lines if a.case == "smoke"}
    assert (smoke["a/good", 1].outcome, smoke["a/good", 1].kind) == (
        "failed",
        "timeout",
    )
    assert smoke["a/weak", 1].outcome == "transient"
    assert smoke["a/weak", 2].outcome == "passed"


def test_a_restart_skips_finished_cases_and_records_an_interrupted_one(
    tmp_path: Path,
) -> None:
    """A folder with no line is a run the last runner was stopped during: its spend counts and it runs again."""
    sweep = _sweep(tmp_path, {}, [GOOD])
    log = AttemptLog(sweep.out / "attempts.jsonl")
    log.append(Attempt("a/good", "smoke", 1, "passed", cost=0.1))
    interrupted = sweep.out / "a__good" / "pdf-brief" / "1"
    interrupted.mkdir(parents=True)
    (interrupted / "spend.json").write_text('{"dollars": 0.25}', encoding="utf-8")

    Runner(sweep).run()

    assert sorted((r["case"], r["attempt"]) for r in _trace(tmp_path)) == [
        ("board-pack", 1),
        ("pdf-brief", 2),
    ]
    lines = log.read()
    assert [
        (a.case, a.outcome, a.cost) for a in lines if a.outcome == "interrupted"
    ] == [("pdf-brief", "interrupted", 0.25)]
    assert _results(tmp_path)["models"][0]["level"] == "agent"


def test_harness_faults_in_a_row_stop_the_sweep(tmp_path: Path) -> None:
    """A broken harness would otherwise mark every model unresolved."""
    models = [_model(f"m/{n}") for n in range(8)]
    plan = {f"m/{n}|smoke": ["harness"] * 3 for n in range(8)}

    Runner(_sweep(tmp_path, plan, models, guard=RamGuard(lanes=1))).run()

    assert len(_trace(tmp_path)) == HARNESS_STREAK
    log = (tmp_path / "sweep" / "runner.log").read_text("utf-8")
    assert f"{HARNESS_STREAK} harness faults in a row" in log


def test_an_account_refusal_stops_the_sweep_and_the_case_runs_again_on_resume(
    tmp_path: Path,
) -> None:
    """Out of credits, nothing more starts and no model is marked down for it; the same command resumes."""
    plan = {"a/good|smoke": ["account", "passed"]}
    sweep = _sweep(tmp_path, plan, [GOOD, WEAK], guard=RamGuard(lanes=1))

    Runner(sweep).run()

    assert [(r["model"], r["case"]) for r in _trace(tmp_path)] == [("a/good", "smoke")]
    shown = report.read(tmp_path / "sweep")
    assert (shown.done, shown.below) == (0, 0)
    assert "refused the account" in shown.text()

    Runner(_sweep(tmp_path, plan, [GOOD, WEAK], guard=RamGuard(lanes=1))).run()

    rows = {row["id"]: row for row in _results(tmp_path)["models"]}
    assert (rows["a/good"]["level"], rows["a/good"]["attempts"]) == ("agent", 4)
    assert rows["a/weak"]["level"] == "agent"


def test_a_second_runner_on_the_same_folder_refuses_to_start(tmp_path: Path) -> None:
    """Resuming while the first still runs would record its live case as interrupted and pay for it twice."""
    sweep = _sweep(tmp_path, {}, [GOOD], guard=RamGuard(lanes=1))
    sweep.child_env["STAND_IN_SECONDS"] = "1.0"
    first = threading.Thread(target=Runner(sweep).run)
    first.start()
    trace = tmp_path / "trace"
    deadline = time.monotonic() + 30
    while not (trace.is_dir() and any(trace.iterdir())):
        assert time.monotonic() < deadline, "the first runner never started its case"
        time.sleep(0.05)

    try:
        with pytest.raises(SweepBusyError, match=f"pid {os.getpid()}"):
            Runner(_sweep(tmp_path, {}, [GOOD], guard=RamGuard(lanes=1))).run()
    finally:
        first.join()

    lines = AttemptLog(sweep.out / "attempts.jsonl").read()
    assert [(a.case, a.number, a.outcome) for a in lines] == [
        ("smoke", 1, "passed"),
        ("pdf-brief", 1, "passed"),
        ("board-pack", 1, "passed"),
    ]


@pytest.mark.skipif(os.name != "nt", reason="a Windows console's Ctrl-C")
def test_a_first_ctrl_c_lets_the_case_in_flight_finish(tmp_path: Path) -> None:
    """A terminal's Ctrl-C reaches every process on its console; the case must not take it as its own."""
    hidden = subprocess.STARTUPINFO(
        dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0
    )

    subprocess.run(
        [sys.executable, "-m", "tests.live.sweep.ctrl_c_sweep", str(tmp_path)],
        cwd=BACKEND,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
        startupinfo=hidden,
        timeout=120,
        check=True,
    )

    lines = AttemptLog(tmp_path / "sweep" / "attempts.jsonl").read()
    assert [(a.case, a.outcome, a.reason) for a in lines] == [("smoke", "passed", "")]
    log = (tmp_path / "sweep" / "runner.log").read_text("utf-8")
    assert "Ctrl-C: no new cases" in log


def test_the_report_reads_progress_from_the_sweeps_files(tmp_path: Path) -> None:
    """Progress is read from disk, so it works while the runner runs or after."""
    Runner(_sweep(tmp_path, {"a/weak|smoke": ["failed"]}, [GOOD, WEAK, SPLIT])).run()

    shown = report.read(tmp_path / "sweep")

    assert (shown.done, shown.passing, shown.below, shown.left) == (3, 2, 1, 0)
    assert shown.runner == "not running"
    text = shown.text()
    assert "3 done of 3 (2 agent, 1 below)" in text
    assert "spent: $0.70 of $100.00" in text
