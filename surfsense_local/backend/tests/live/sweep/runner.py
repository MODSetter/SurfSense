"""The sweep's loop: start ready cases in free lanes while RAM and the budget allow, and record each as it ends.

A lane is one pytest process with its own data dir, temp dirs and block of
ports; a model's two scored cases may take two lanes at once. Every decision
goes to runner.log with the free memory then. Ctrl-C stops new starts and waits
for the cases in flight; a second Ctrl-C kills them, and a restarted sweep
records them as interrupted and runs them again.
"""

import os
import queue
import shutil
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psutil

from tests.live.lane_ports import lane_block_base
from tests.live.sweep import report, results
from tests.live.sweep.attempt import Attempt, classify, ledger_dollars
from tests.live.sweep.attempt_log import AttemptLog
from tests.live.sweep.budget import Budget, estimate
from tests.live.sweep.model_list import ListedModel
from tests.live.sweep.plan import CASES, Next, plan, rolls
from tests.live.sweep.process import Process, run_case
from tests.live.sweep.ram_guard import RamGuard

GB = 1 << 30
# Harness faults in a row, across models, that stop the sweep: then the harness is broken, not the models.
HARNESS_STREAK = 6
# The real pytest command, or a test's stand-in: (case, lane dir) -> argv.
CommandFor = Callable[[str, Path], list[str]]


@dataclass
class Running:
    model: ListedModel
    case: str
    number: int
    lane: int
    attempt_dir: Path
    expected: float
    capped_by_case: bool
    started: float
    kill: threading.Event = field(default_factory=threading.Event)
    working_set: int = 0
    thread: threading.Thread | None = None

    def in_flight_dollars(self) -> float:
        """What it is expected to cost, or what it has already spent if that is more."""
        return max(self.expected, ledger_dollars(self.attempt_dir))


@dataclass
class Sweep:
    """Where the sweep writes, what it runs, what each child is given, and the limits it keeps."""

    out: Path
    models: list[ListedModel]
    assumed: list[ListedModel]
    listing: dict[str, Any]
    command_for: CommandFor
    child_env: dict[str, str]
    cwd: Path
    guard: RamGuard
    budget: Budget
    case_seconds: float = 20 * 60
    retry_unresolved: bool = False
    available_bytes: Callable[[], int] = lambda: psutil.virtual_memory().available
    poll_seconds: float = 1.0
    progress_seconds: float = 300.0
    say: Callable[[str], None] = print


class Runner:
    def __init__(self, sweep: Sweep) -> None:
        self.sweep = sweep
        self.attempt_log = AttemptLog(sweep.out / "attempts.jsonl")
        self.attempts = self.attempt_log.read()
        self.running: dict[tuple[str, str], Running] = {}
        self.finished: queue.Queue[tuple[Running, Process]] = queue.Queue()
        self.stopping = False
        self.ended_here: list[Attempt] = []
        self._said_waiting = ""
        self._say_again = 0.0
        self.log_path = sweep.out / "runner.log"
        self.started = time.time()

    def run(self) -> list[dict[str, Any]]:
        """Until every model has its verdict, the budget is spent, or Ctrl-C."""
        sweep = self.sweep
        sweep.out.mkdir(parents=True, exist_ok=True)
        self._record_interrupted()
        if sweep.retry_unresolved:
            self._reopen_unresolved()
        self.log(
            f"start: {len(sweep.models)} models, up to {sweep.guard.lanes} lanes, "
            f"${sweep.budget.cap:.2f} budget, ${sweep.budget.case_cap:.2f} per case"
        )
        self._save()
        next_progress = time.monotonic() + sweep.progress_seconds
        interrupts = 0
        while True:
            try:
                self._collect()
                if self.stopping and not self.running:
                    break
                units = [] if self.stopping else self._units()
                if not units and not self.running:
                    break
                if units and not self._launch(units) and not self.running:
                    self.log("budget reached: no case fits what is left")
                    break
                if time.monotonic() >= next_progress:
                    self.sweep.say(report.read(sweep.out).text())
                    next_progress += sweep.progress_seconds
                time.sleep(sweep.poll_seconds)
            except KeyboardInterrupt:
                interrupts += 1
                self.stopping = True
                if interrupts == 1:
                    self.log("Ctrl-C: no new cases; waiting for the ones in flight")
                else:
                    self.log("Ctrl-C again: killing the cases in flight")
                    for running in self.running.values():
                        running.kill.set()
        for running in list(self.running.values()):
            if running.thread is not None:
                running.thread.join()
        self._collect()
        rows = self._save()
        self._write_status(ended=True)
        self.log("done")
        return rows

    def _units(self) -> list[tuple[ListedModel, Next]]:
        """Every case some model should run next, in the models' order, whether or not its pause is over."""
        grouped = results.by_model(self.attempts)
        units = []
        for model in self.sweep.models:
            flying = {case for (mid, case) in self.running if mid == model.id}
            made = plan(grouped.get(model.id, {}), flying)
            units += [(model, n) for n in made.next]
        return units

    def _launch(self, units: list[tuple[ListedModel, Next]]) -> bool:
        """Start what fits now; False when nothing could start for the budget alone."""
        budget_only = True
        now = time.time()
        for model, unit in units:
            if unit.not_before > now:
                budget_only = False
                continue
            lane = self._free_lane()
            if lane is None:
                return True
            spent = sum(a.cost for a in self.attempts)
            in_flight = [r.in_flight_dollars() for r in self.running.values()]
            expected = estimate(model, unit.case)
            if not self.sweep.budget.may_start(spent, in_flight, expected):
                continue
            budget_only = False
            available = self.sweep.available_bytes() / GB
            running_gb = [r.working_set / GB for r in self.running.values()]
            if not self.sweep.guard.may_start(available, running_gb):
                # Once per change in what runs, and every five minutes while it waits.
                said = f"{len(running_gb)} running, lane {self.sweep.guard.lane_gb} GB"
                if said != self._said_waiting or time.monotonic() > self._say_again:
                    self.log(f"waiting for RAM: {available:.1f} GB free, {said}")
                    self._said_waiting = said
                    self._say_again = time.monotonic() + 300
                return True
            stop, capped = self.sweep.budget.stop_for(spent, in_flight)
            self._start(model, unit.case, lane, expected, stop, capped, available)
        return not budget_only

    def _free_lane(self) -> int | None:
        taken = {r.lane for r in self.running.values()}
        free = [n for n in range(self.sweep.guard.lanes) if n not in taken]
        return free[0] if free else None

    def _start(
        self,
        model: ListedModel,
        case: str,
        lane: int,
        expected: float,
        stop: float,
        capped: bool,
        available: float,
    ) -> None:
        number = self._next_number(model.id, case)
        attempt_dir = self.sweep.out / model.folder / case / str(number)
        if attempt_dir.exists():
            aside = attempt_dir.with_name(f"{number}-stale-{int(time.time())}")
            attempt_dir.rename(aside)
        attempt_dir.mkdir(parents=True)
        lane_dir = self.sweep.out / ".lanes" / str(lane)
        shutil.rmtree(lane_dir, ignore_errors=True)
        for sub in ("data", "temp"):
            (lane_dir / sub).mkdir(parents=True, exist_ok=True)
        env = {
            **self.sweep.child_env,
            "SURFSENSE_LIVE_TESTS": "1",
            "SURFSENSE_LIVE_PROVIDER": "openrouter",
            "SURFSENSE_LIVE_MODEL": model.id,
            "SURFSENSE_LIVE_RUNS_DIR": str(attempt_dir),
            "SURFSENSE_LIVE_STOP_DOLLARS": f"{stop:.4f}",
            "SURFSENSE_LIVE_PORT_BASE": str(lane_block_base(lane + 1)),
            "SURFSENSE_LOCAL_DATA_DIR": str(lane_dir / "data"),
            # LibreOffice profiles and other temp files go with the lane.
            "TEMP": str(lane_dir / "temp"),
            "TMP": str(lane_dir / "temp"),
            "PYTHON_DOTENV_DISABLED": "1",
        }
        command = self.sweep.command_for(case, lane_dir)
        running = Running(
            model, case, number, lane, attempt_dir, expected, capped, time.time()
        )

        def sampled(now: int) -> None:
            running.working_set = now

        def work() -> None:
            try:
                process = run_case(
                    command,
                    env=env,
                    cwd=self.sweep.cwd,
                    log=attempt_dir / "pytest.log",
                    time_limit=self.sweep.case_seconds,
                    lane=lane,
                    kill=running.kill,
                    on_sample=sampled,
                )
            except OSError as failure:
                process = Process(exit_code=None, seconds=0.0, lane=lane)
                self.log(f"{model.id} {case}: could not start: {failure}")
            self.finished.put((running, process))

        running.thread = threading.Thread(target=work, daemon=True)
        self.running[(model.id, case)] = running
        self.log(
            f"start {model.id} {case} #{number} in lane {lane} ({available:.1f} GB free, "
            f"expect ${expected:.3f}, stop ${stop:.2f})"
        )
        running.thread.start()
        self._write_status()

    def _collect(self) -> None:
        while True:
            try:
                running, process = self.finished.get_nowait()
            except queue.Empty:
                return
            self.running.pop((running.model.id, running.case), None)
            if running.kill.is_set():
                self.log(
                    f"{running.model.id} {running.case} #{running.number}: killed, "
                    "run again on restart"
                )
                self._write_status()
                continue
            ending = classify(
                running.attempt_dir,
                process,
                self.sweep.out,
                capped_by_case=running.capped_by_case,
            )
            attempt = Attempt(
                model=running.model.id,
                case=running.case,
                number=running.number,
                outcome=ending.outcome,
                kind=ending.kind,
                reason=ending.reason,
                cost=round(ending.cost, 4),
                reported=ending.reported,
                minutes=round(process.seconds / 60, 2),
                run_folder=ending.run_folder,
                served_by=ending.served_by,
                peak_mb=process.peak_mb,
                lane=process.lane,
                ended=time.time(),
            )
            self._record(attempt)

    def _record(self, attempt: Attempt) -> None:
        self.attempt_log.append(attempt)
        self.attempts.append(attempt)
        self.ended_here.append(attempt)
        if attempt.peak_mb is not None:
            change = self.sweep.guard.observe(attempt.peak_mb / 1024)
            if change:
                self.log(change)
        self.log(
            f"end {attempt.model} {attempt.case} #{attempt.number}: {attempt.outcome}"
            f"{f' ({attempt.kind})' if attempt.kind else ''} in {attempt.minutes:.1f} min, "
            f"peak {attempt.peak_mb} MB, ${attempt.cost:.3f}"
            f"{f' - {attempt.reason}' if attempt.reason else ''}"
        )
        if attempt.outcome == "budget":
            self.log("budget reached mid-run: no new cases")
            self.stopping = True
        streak = self.ended_here[-HARNESS_STREAK:]
        if len(streak) == HARNESS_STREAK and all(
            a.outcome == "harness" for a in streak
        ):
            self.log(
                f"{HARNESS_STREAK} harness faults in a row: stopping; "
                f"see {attempt.run_folder}/pytest.log"
            )
            self.stopping = True
        self._save()

    def _next_number(self, model_id: str, case: str) -> int:
        numbers = [
            a.number for a in self.attempts if a.model == model_id and a.case == case
        ]
        return max(numbers, default=0) + 1

    def _record_interrupted(self) -> None:
        """An attempt folder with no line is a run the last runner was stopped during; its spend still counts."""
        known = {(a.model, a.case, a.number) for a in self.attempts}
        for model in self.sweep.models:
            for case in CASES:
                folder = self.sweep.out / model.folder / case
                if not folder.is_dir():
                    continue
                for attempt_dir in sorted(folder.iterdir()):
                    if not attempt_dir.name.isdigit():
                        continue
                    number = int(attempt_dir.name)
                    if (model.id, case, number) in known:
                        continue
                    self._append(
                        Attempt(
                            model=model.id,
                            case=case,
                            number=number,
                            outcome="interrupted",
                            cost=round(ledger_dollars(attempt_dir), 4),
                            run_folder=attempt_dir.relative_to(
                                self.sweep.out
                            ).as_posix(),
                            ended=time.time(),
                        )
                    )
                    self.log(f"{model.id} {case} #{number}: interrupted, run again")

    def _reopen_unresolved(self) -> None:
        """--retry-unresolved: each unresolved case gets its retries back."""
        grouped = results.by_model(self.attempts)
        for model in self.sweep.models:
            for case, attempts in grouped.get(model.id, {}).items():
                found = rolls(attempts)
                if found and found[-1].outcome == "unresolved":
                    self._append(
                        Attempt(model.id, case, 0, "reopened", ended=time.time())
                    )
                    self.log(f"{model.id} {case}: reopened")

    def _append(self, attempt: Attempt) -> None:
        self.attempt_log.append(attempt)
        self.attempts.append(attempt)

    def _save(self) -> list[dict[str, Any]]:
        running: dict[str, set[str]] = {}
        for model_id, case in self.running:
            running.setdefault(model_id, set()).add(case)
        rows = results.write(
            self.sweep.out,
            self.sweep.models,
            self.attempts,
            self.sweep.assumed,
            running,
            self.sweep.listing,
        )
        self._write_status()
        return rows

    def _write_status(self, ended: bool = False) -> None:
        results.write_atomic(
            self.sweep.out / report.STATUS,
            {
                # None once the runner has finished, so a report never takes a reused pid for it.
                "pid": None if ended else os.getpid(),
                "updated": _now(),
                "started": self.started,
                "lanes": self.sweep.guard.lanes,
                "lane_gb": self.sweep.guard.lane_gb,
                "budget": self.sweep.budget.cap,
                "case_cap": self.sweep.budget.case_cap,
                "running": [
                    {
                        "model": r.model.id,
                        "case": r.case,
                        "number": r.number,
                        "lane": r.lane,
                        "started": r.started,
                    }
                    for r in self.running.values()
                ],
            },
        )

    def log(self, line: str) -> None:
        """One decision, stamped with the time and the free memory then."""
        free = self.sweep.available_bytes() / GB
        stamped = f"{_now()} [{free:.1f} GB free] {line}"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as log:
            log.write(stamped + "\n")
        self.sweep.say(stamped)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
