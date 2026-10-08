"""What one attempt at a (model, case) came to, read from its run folder and its process.

`passed` and `failed` are the model's. `transient` (the provider failed) and
`harness` (our fault: no result.json, a crash, an app error, the thread opened
as a chat) are tried again and never counted. `budget` is the sweep's money
running out, `account` OpenRouter refusing the key or its credits, and
`interrupted` an attempt the runner was stopped during; none is counted or uses
up a retry, and the first two stop the sweep. `reopened` is not a run: it gives
an unresolved case its retries back.
"""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from tests.live.sweep.process import Process
from tests.live.sweep.retry_rule import (
    account_refused,
    context_overflow,
    ended_by_provider,
)

Outcome = Literal[
    "passed",
    "failed",
    "transient",
    "harness",
    "budget",
    "account",
    "interrupted",
    "reopened",
]
# The proxy's refusal once a run reaches its stop (recording_proxy.py, conftest.py).
_BUDGET_STOP = "live budget stop"


@dataclass(frozen=True)
class Attempt:
    model: str
    case: str
    number: int
    outcome: Outcome
    kind: str | None = None
    reason: str = ""
    # OpenRouter's own bill when every request carried one, else the ledger's.
    cost: float = 0.0
    reported: bool = False
    minutes: float = 0.0
    run_folder: str = ""
    served_by: list[str] = field(default_factory=list)
    peak_mb: int | None = None
    lane: int | None = None
    # Epoch seconds; a retry waits from here.
    ended: float = 0.0

    @property
    def counted(self) -> bool:
        return self.outcome in ("passed", "failed")

    @property
    def uses_a_try(self) -> bool:
        return self.outcome in ("transient", "harness")

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> "Attempt":
        return cls(**raw)


@dataclass(frozen=True)
class Ending:
    """An attempt's outcome and what it cost, before the runner names it."""

    outcome: Outcome
    kind: str | None = None
    reason: str = ""
    cost: float = 0.0
    reported: bool = False
    run_folder: str = ""
    served_by: list[str] = field(default_factory=list)


def classify(
    attempt_dir: Path, process: Process, root: Path, *, capped_by_case: bool
) -> Ending:
    """The attempt's ending; `capped_by_case` says the run's stop was the per-case cap, not the sweep's last dollars."""
    run = _run_folder(attempt_dir)
    cost, reported = _cost(attempt_dir, run)
    exchanges = _json_list(run / "model-requests.json") if run else []
    base = {
        "cost": cost,
        "reported": reported,
        "run_folder": (run or attempt_dir).relative_to(root).as_posix(),
        "served_by": _served_by(exchanges),
    }
    refused = next((e for e in exchanges if account_refused(e)), None)
    if refused is not None and not _passed(run):
        said = refused.get("error") or f"HTTP {refused.get('status')}"
        return Ending(
            "account", reason=f"OpenRouter refused the account: {said}"[:300], **base
        )
    if process.timed_out:
        if _output_tokens(attempt_dir) > 0:
            return Ending("failed", "timeout", "ran past the case's time limit", **base)
        return Ending(
            "transient", "timeout", "timed out with no output from the model", **base
        )
    if _says(attempt_dir, run, _BUDGET_STOP):
        if capped_by_case:
            return Ending(
                "failed", "case-cap", "spent past the per-case dollar cap", **base
            )
        return Ending("budget", reason="the sweep's budget ran out mid-run", **base)
    if run is None or not (run / "result.json").is_file():
        return Ending("harness", reason="no result.json", **base)
    result = _json(run / "result.json")
    if process.exit_code not in (0, 1):
        return Ending("harness", reason=f"pytest exit {process.exit_code}", **base)
    if _opened_as_a_chat(attempt_dir):
        # opencode never served this run, so the model was asked without the agent's tools.
        return Ending(
            "harness",
            reason="the thread opened as a chat: the agent was not ready",
            **base,
        )
    outcome = result.get("outcome")
    detail = result.get("detail") or ""
    if outcome == "passed":
        return Ending("passed", **base)
    if outcome == "skipped":
        return Ending("harness", reason=f"skipped: {detail[-200:]}", **base)
    timed_out_prints = [
        f
        for f in (result.get("word_previews") or {}).get("failures", [])
        if "Timeout" in f
    ]
    if timed_out_prints:
        return Ending(
            "harness", reason=f"a print timed out: {timed_out_prints[0]}", **base
        )
    if "HTTPStatusError" in detail:
        return Ending("harness", reason=f"app error: {_short(detail)}", **base)
    if not exchanges:
        return Ending("harness", reason="failed before the first model request", **base)
    turns = _json_list(run / "frames.json")
    if context_overflow(exchanges[-1]):
        return Ending("failed", "context-overflow", _short(detail), **base)
    if ended_by_provider(exchanges, turns):
        return Ending(
            "transient", reason=(exchanges[-1].get("error") or "")[:300], **base
        )
    return Ending("failed", reason=_short(detail), **base)


def ledger_dollars(attempt_dir: Path) -> float:
    """What the attempt's own ledger has charged so far."""
    ledger = _ledger(attempt_dir)
    return float(ledger.get("dollars") or 0.0)


def _passed(run: Path | None) -> bool:
    result = run / "result.json" if run else None
    return bool(
        result and result.is_file() and _json(result).get("outcome") == "passed"
    )


def _run_folder(attempt_dir: Path) -> Path | None:
    """The one run folder RunFolder made inside the attempt's runs dir."""
    if not attempt_dir.is_dir():
        return None
    made = sorted(
        p for p in attempt_dir.iterdir() if p.is_dir() and not p.name.startswith(".")
    )
    return made[-1] if made else None


def _cost(attempt_dir: Path, run: Path | None) -> tuple[float, bool]:
    """OpenRouter's reported bill, else the run's cost.json, else the ledger a killed run leaves."""
    if run is not None and (run / "cost.json").is_file():
        cost = _json(run / "cost.json")
        if cost.get("reported_dollars") is not None:
            return float(cost["reported_dollars"]), True
        return float(cost.get("dollars") or 0.0), False
    return ledger_dollars(attempt_dir), False


def _ledger(attempt_dir: Path) -> dict[str, Any]:
    path = attempt_dir / "spend.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _output_tokens(attempt_dir: Path) -> int:
    """Tokens the model wrote, from the ledger the proxy updates on every call."""
    models = _ledger(attempt_dir).get("by_model") or {}
    return sum(int(entry.get("output_tokens") or 0) for entry in models.values())


def _served_by(exchanges: list[dict[str, Any]]) -> list[str]:
    """OpenRouter's upstream providers, in the order they first served."""
    seen: list[str] = []
    for exchange in exchanges:
        name = exchange.get("served_by")
        if name and name not in seen:
            seen.append(name)
    return seen


def _says(attempt_dir: Path, run: Path | None, text: str) -> bool:
    """Whether the pytest log or the turns' frames carry this text."""
    places = [attempt_dir / "pytest.log"]
    if run is not None:
        places.append(run / "frames.json")
    return any(
        path.is_file() and text in path.read_text(encoding="utf-8", errors="replace")
        for path in places
    )


def _opened_as_a_chat(attempt_dir: Path) -> bool:
    """The app's warning, kept in the case's pytest.log, that a thread fell back to the chat."""
    log = attempt_dir / "pytest.log"
    return log.is_file() and "opens as a chat:" in log.read_text(
        encoding="utf-8", errors="replace"
    )


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_list(path: Path) -> list[Any]:
    return _json(path) if path.is_file() else []


def _short(detail: str) -> str:
    """The failing assertion's message: the last `E   ` lines of pytest's report."""
    lines = [
        line[4:].strip() for line in detail.splitlines() if line.startswith("E   ")
    ]
    return " ".join(lines[:2])[:300] if lines else detail[-300:]
