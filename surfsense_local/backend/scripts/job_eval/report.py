"""Every run's record rolled up per case and model: the rows a job page may cite, failures included."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


def report(out: Path) -> str:
    runs = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(out.glob("*/run.json"))
    ]
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for record in runs:
        grouped[(record["case"], record["model"])].append(record)
    lines = [
        "| case | model | runs | correct (per run) | accuracy | false Yes | other wrong answers | Yes without quote | dropdown or integrity problems | $ first run | $ per run | seconds per run |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for (case, model), records in sorted(grouped.items()):
        records.sort(key=lambda r: r["started"])
        scored = sum(r["scored_rows"] for r in records)
        correct = sum(r["correct"] for r in records)
        problems = sum(r["dropdown_violations"] + len(r["integrity"]) for r in records)
        per_run = ", ".join(f"{r['correct']}/{r['scored_rows']}" for r in records)
        lines.append(
            f"| {case} | {model} | {len(records)} | {per_run} | {correct / scored:.1%} | "
            f"{sum(r['false_yes'] for r in records)} | {sum(_other_wrong(r) for r in records)} | "
            f"{sum(r['yes_without_quote'] for r in records)} | {problems} | "
            # The first run pays to fill the provider's cache; later ones read it.
            f"{records[0]['spend']['dollars']:.4f} | "
            f"{sum(r['spend']['dollars'] for r in records) / len(records):.4f} | "
            f"{sum(r['seconds'] for r in records) / len(records):.0f} |"
        )
    statuses = sorted({r["gold_status"] for r in runs})
    lines.append("")
    lines.append(f"Gold status: {', '.join(statuses)}. Misses by gold>answer:")
    for (case, model), records in sorted(grouped.items()):
        misses: dict[str, int] = defaultdict(int)
        for record in records:
            for kind, count in record["misses"].items():
                misses[kind] += count
        if misses:
            listed = ", ".join(
                f"{kind} {count}" for kind, count in sorted(misses.items())
            )
            lines.append(f"- {case} on {model}: {listed}")
    return "\n".join(lines) + "\n"


def _other_wrong(record: dict) -> int:
    """Written answers other than Yes that the gold does not give: a wrong No or N/A."""
    return sum(
        count
        for kind, count in record["misses"].items()
        if kind.split(">")[1] not in ("Yes", "Needs review", "unreached")
    )
