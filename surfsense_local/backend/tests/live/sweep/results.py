"""The sweep's output for the catalog: a summary per model and sweep-results.json, rewritten whole after every attempt.

It does not write capabilities.json: the catalog's own generator owns that shape.
"""

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tests.live.sweep.attempt import Attempt
from tests.live.sweep.model_list import ListedModel
from tests.live.sweep.plan import CASES, plan

RESULTS = "sweep-results.json"
SUMMARY = "summary.json"


def by_model(attempts: list[Attempt]) -> dict[str, dict[str, list[Attempt]]]:
    """Each model's attempts, by case, in the order they ended."""
    grouped: dict[str, dict[str, list[Attempt]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for attempt in attempts:
        grouped[attempt.model][attempt.case].append(attempt)
    return grouped


def summary(
    model: ListedModel, by_case: dict[str, list[Attempt]], running: set[str]
) -> dict[str, Any]:
    """One model's row: its cells, verdict, cost, time, upstreams and notes."""
    made = plan(by_case, running)
    ran = [
        a for case in CASES for a in by_case.get(case, []) if a.outcome != "reopened"
    ]
    verdict = made.verdict
    if verdict is not None:
        status = "done" if verdict.level is not None else "unresolved"
    else:
        status = "running" if ran or running else "pending"
    served: list[str] = []
    for attempt in ran:
        served += [name for name in attempt.served_by if name not in served]
    cells = verdict.cells if verdict else {}
    return {
        "id": model.id,
        "key": model.key,
        "reads_images": model.reads_images,
        "status": status,
        "level": verdict.level if verdict else None,
        "smoke": cells.get("smoke"),
        "pdf_brief": cells.get("pdf-brief"),
        "board_pack": cells.get("board-pack"),
        "passed": verdict.passed if verdict else None,
        "counted": verdict.counted if verdict else None,
        "run": verdict.run if verdict else None,
        "cost": round(sum(a.cost for a in ran), 4),
        "minutes": round(sum(a.minutes for a in ran), 1),
        "attempts": len(ran),
        "served_by": served,
        "notes": verdict.notes if verdict else [],
        "measured_on": _day(max((a.ended for a in ran), default=0.0)),
        "prices_per_million": {"input": model.prompt, "output": model.completion},
        "context_length": model.context_length,
        # The run that decided each case, under the sweep's folder.
        "runs": {
            case: [a for a in by_case[case] if a.counted][-1].run_folder
            for case in CASES
            if any(a.counted for a in by_case.get(case, []))
        },
    }


def assumed_row(model: ListedModel) -> dict[str, Any]:
    """A flagship taken at agent level without a run, saying so."""
    return {
        "id": model.id,
        "key": model.key,
        "reads_images": model.reads_images,
        "level": "agent",
        "assumed": True,
        "prices_per_million": {"input": model.prompt, "output": model.completion},
        "context_length": model.context_length,
        "notes": [f"input ${model.prompt:g}/M: assumed to pass, not run"],
    }


def write(
    out: Path,
    models: list[ListedModel],
    attempts: list[Attempt],
    assumed: list[ListedModel],
    running: dict[str, set[str]],
    listing: dict[str, Any],
) -> list[dict[str, Any]]:
    """Each started model's summary.json and the whole sweep-results.json; returns the rows."""
    grouped = by_model(attempts)
    rows = []
    for model in models:
        row = summary(model, grouped.get(model.id, {}), running.get(model.id, set()))
        rows.append(row)
        if row["status"] != "pending":
            write_atomic(out / model.folder / SUMMARY, row)
    write_atomic(
        out / RESULTS,
        {
            "generated": datetime.now(UTC).isoformat(timespec="seconds"),
            "suite": "screening",
            "cases": list(CASES),
            "listing": listing,
            "spent": round(sum(a.cost for a in attempts), 4),
            "models": rows,
            "assumed": [assumed_row(model) for model in assumed],
        },
    )
    return rows


def write_atomic(path: Path, data: Any) -> None:
    """Replaced whole, so a kill mid-write never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f".{path.name}.partial")
    partial.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", "utf-8")
    partial.replace(path)


def _day(epoch: float) -> str | None:
    if not epoch:
        return None
    return datetime.fromtimestamp(epoch, UTC).date().isoformat()
