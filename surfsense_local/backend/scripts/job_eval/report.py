"""Every run's record rolled up per case and model: the rows a job page may cite, failures included."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from job_eval.contract_report import contract_report


def report(out: Path) -> str:
    runs = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(out.glob("*/run.json"))
    ]
    if runs and all(r.get("kind") == "contract" for r in runs):
        return contract_report(runs)
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for record in runs:
        grouped[(record["case"], _model(record))].append(record)
    lines = [
        "| case | model | runs | correct (per run) | accuracy | with the provider setting flipped | false Yes | other wrong answers | Yes without quote | suggestions right, wrong | dropdown or integrity problems | $ first run | $ per run | seconds per run |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for (case, model), records in sorted(grouped.items()):
        records.sort(key=lambda r: r["started"])
        scored = sum(r["scored_rows"] for r in records)
        correct = sum(r["correct"] for r in records)
        problems = sum(r["dropdown_violations"] + len(r["integrity"]) for r in records)
        per_run = ", ".join(f"{r['correct']}/{r['scored_rows']}" for r in records)
        # A case whose gold lists no rows scores none, and has no accuracy to give.
        accuracy = f"{correct / scored:.1%}" if scored else "—"
        lines.append(
            f"| {case} | {model} | {len(records)} | {per_run} | {accuracy} | "
            f"{_flipped(records, scored)} | "
            f"{sum(r['false_yes'] for r in records)} | {sum(_other_wrong(r) for r in records)} | "
            f"{sum(r['yes_without_quote'] for r in records)} | "
            f"{sum(r.get('suggested_right', 0) for r in records)}, "
            f"{sum(r.get('suggested_wrong', 0) for r in records)} | {problems} | "
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


def _model(record: dict) -> str:
    """The model, and whatever else sets a run apart: its checker, the firm settings it ran with,
    and the run's options where they differ from the defaults, so no line pools two kinds."""
    checker = record.get("checker")
    settings = record.get("settings") or {}
    on = sorted(k for k, v in (settings.get("job") or {}).items() if v)
    options = [
        f"reasoning {settings['reasoning']}"
        if settings.get("reasoning") not in (None, "default")
        else "",
        f"effort {settings['effort']}"
        if record["model"].startswith("anthropic:")
        and settings.get("effort") not in (None, "low")
        else "",
        f"embedder {settings['embedder']}"
        if settings.get("embedder") not in (None, "bge")
        else "",
        "all rows" if settings.get("all_rows") else "",
    ]
    return (
        record["model"]
        + (f", checked by {checker}" if checker else "")
        + (f", with {', '.join(on)} on" if on else "")
        + "".join(f", {option}" for option in options if option)
    )


def _flipped(records: list[dict], scored: int) -> str:
    """Accuracy had the provider setting been the other way round; runs before it, and a case
    with no scored rows, say "—"."""
    flips = [r.get("provider_setting_flipped") for r in records]
    if not scored or not all(flips):
        return "—"
    turned = "on" if flips[0]["provider_on"] else "off"
    return f"{sum(f['correct'] for f in flips) / scored:.1%} ({turned})"


def _other_wrong(record: dict) -> int:
    """Written answers other than Yes that the gold does not give: a wrong No or N/A."""
    return sum(
        count
        for kind, count in record["misses"].items()
        if kind.split(">")[1] not in ("Yes", "Needs review", "unreached")
    )
