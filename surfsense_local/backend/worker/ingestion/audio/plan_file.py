"""The windows a recording is cut into, written once the speech pass ends: a
job that finds it skips the pass, and one that does not decodes again."""

import json
from dataclasses import dataclass
from pathlib import Path

from worker.ingestion.audio.windows import Window

__all__ = ["Plan", "read_plan", "write_plan"]

_VERSION = 1


@dataclass(frozen=True)
class Plan:
    # The decoded recording's length.
    seconds: float
    windows: list[Window]


def write_plan(path: Path, plan: Plan) -> None:
    """Replaced whole, so a reader never sees half a plan."""
    partial = path.with_name(f"{path.name}.partial")
    partial.write_text(
        json.dumps(
            {
                "version": _VERSION,
                "seconds": plan.seconds,
                "windows": [[w.start_s, w.end_s] for w in plan.windows],
            }
        ),
        encoding="utf-8",
    )
    partial.replace(path)


def read_plan(path: Path) -> Plan | None:
    """None when there is no complete plan of this version."""
    try:
        kept = json.loads(path.read_text(encoding="utf-8"))
        if kept["version"] != _VERSION:
            return None
        return Plan(
            float(kept["seconds"]),
            [Window(float(start), float(end)) for start, end in kept["windows"]],
        )
    except (OSError, ValueError, TypeError, KeyError):
        return None
