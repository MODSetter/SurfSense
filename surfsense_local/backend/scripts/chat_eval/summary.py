"""Runs side by side, so a change is read against its baseline."""

import json
from pathlib import Path

# Each rated over the replies it applies to: a score of None does not count.
METRICS = (
    ("Cut off by the cap", "truncated"),
    ("Empty", "empty"),
    ("Invented a citation", "invented"),
    ("Cited every supporting passage", "cites_support"),
    ("Cited a passage that does not hold the answer", "cites_other"),
    ("States the expected facts", "facts"),
    ("In the question's script", "same_script"),
)


def summarize(paths: list[Path]) -> str:
    """A markdown table with a column per result file and a row per metric."""
    runs = [_read(path) for path in paths]
    lines = [
        "| | " + " | ".join(f"{path.parent.name}/{path.stem}" for path in paths) + " |",
        "|---" * (len(paths) + 1) + "|",
        "| Run | " + " | ".join(_identity(run) for run in runs) + " |",
        "| Replies | " + " | ".join(str(len(run)) for run in runs) + " |",
    ]
    for label, field in METRICS:
        lines.append(
            f"| {label} | " + " | ".join(_rate(run, field) for run in runs) + " |"
        )
    return "\n".join(lines)


def _read(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _identity(run: list[dict]) -> str:
    if not run:
        return ""
    first = run[0]
    runtime = f", llama.cpp {first['runtime']}" if first["runtime"] else ""
    return f"{first['model']} on {first['target']}{runtime}"


def _rate(run: list[dict], field: str) -> str:
    values = [bool(r["score"][field]) for r in run if r["score"][field] is not None]
    if not values:
        return "n/a"
    met = sum(values)
    return f"{100 * met / len(values):.0f}% ({met}/{len(values)})"
