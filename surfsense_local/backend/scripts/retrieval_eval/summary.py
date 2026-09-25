"""Runs side by side, per slice, so a retrieval change is read against a baseline."""

import json
from pathlib import Path


def read(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def summarize(paths: list[Path]) -> str:
    runs = [read(path) for path in paths]
    slices = []
    for run in runs:
        for result in run:
            if result["slice"] not in slices:
                slices.append(result["slice"])

    lines = [
        "| Slice | " + " | ".join(path.stem for path in paths) + " |",
        "|---" * (len(paths) + 1) + "|",
    ]
    for name in [*slices, "all"]:
        cells = []
        for run in runs:
            rows = [r for r in run if name == "all" or r["slice"] == name]
            cells.append(_rate(rows))
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    lines.append(
        "| mean rank when found | " + " | ".join(_mean_rank(run) for run in runs) + " |"
    )
    return "\n".join(lines)


def _rate(rows: list[dict]) -> str:
    """The share whose answer reached the prompt: what chat actually sees."""
    if not rows:
        return "n/a"
    reached = sum(1 for row in rows if row["ranking"]["in_top_5"])
    return f"{100 * reached / len(rows):.0f}% ({reached}/{len(rows)})"


def _mean_rank(run: list[dict]) -> str:
    ranks = [r["ranking"]["rank"] for r in run if r["ranking"]["found"]]
    return f"{sum(ranks) / len(ranks):.1f}" if ranks else "n/a"
