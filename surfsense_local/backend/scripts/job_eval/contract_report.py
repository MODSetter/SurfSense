"""Every contract run's record rolled up per case and model: the rows a job page may cite."""

from __future__ import annotations

from collections import defaultdict


def contract_report(runs: list[dict]) -> str:
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for record in runs:
        grouped[(record["case"], _model(record))].append(record)
    lines = [
        "| case | model | runs | verdicts right | outcomes right | changes right, unneeded, missed | clause found | for a person | integrity problems | $ per run | seconds per run |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    totals: dict[str, list[dict]] = defaultdict(list)
    for (case, model), records in sorted(grouped.items()):
        totals[model] += records
        lines.append(f"| {case} | {model} | {_row(records)}")
    lines.append("| **all cases** | | | | | | | | | | |")
    for model, records in sorted(totals.items()):
        lines.append(f"| **all** | {model} | {_row(records)}")
    statuses = sorted({r["gold_status"] for r in runs})
    lines += ["", f"Gold status: {', '.join(statuses)}. Wrong verdicts by gold>said:"]
    for model, records in sorted(totals.items()):
        misses: dict[str, int] = defaultdict(int)
        for record in records:
            for kind, count in record["misses"].items():
                misses[kind] += count
        listed = ", ".join(f"{k} {n}" for k, n in sorted(misses.items())) or "none"
        lines.append(f"- {model}: {listed}")
    return "\n".join(lines) + "\n"


def _row(records: list[dict]) -> str:
    scored = sum(r["scored_points"] for r in records)
    right = sum(r["correct"] for r in records)
    outcomes = sum(r["outcome_correct"] for r in records)
    changes = {
        k: sum(r["changes"][k] for r in records)
        for k in ("right", "unneeded", "missed")
    }
    found = sum(r["located"][0] for r in records)
    of = sum(r["located"][1] for r in records)
    person = sum(r["counts"]["for_person"] for r in records)
    problems = sum(len(r["integrity"]) for r in records)
    dollars = sum(r["spend"]["dollars"] for r in records) / len(records)
    seconds = sum(r["seconds"] for r in records) / len(records)
    return (
        f"{len(records)} | {right}/{scored} ({_share(right, scored)}) | "
        f"{outcomes}/{scored} ({_share(outcomes, scored)}) | "
        f"{changes['right']}, {changes['unneeded']}, {changes['missed']} | "
        f"{found}/{of} | {person} | {problems} | {dollars:.4f} | {seconds:.0f} |"
    )


def _share(part: int, whole: int) -> str:
    return f"{part / whole:.1%}" if whole else "—"


def _model(record: dict) -> str:
    """The model, and whatever else sets a run apart, so no line pools two kinds of run."""
    settings = record.get("settings") or {}
    on = sorted(k for k, v in (settings.get("job") or {}).items() if v)
    checker = record.get("checker")
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
    ]
    return (
        record["model"]
        + (f", checked by {checker}" if checker else "")
        + (f", with {', '.join(on)} on" if on else "")
        + "".join(f", {option}" for option in options if option)
    )
