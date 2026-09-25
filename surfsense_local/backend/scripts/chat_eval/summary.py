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
JUDGED = (
    ("Judge: grounded", "grounded"),
    ("Judge: complete", "complete"),
    ("Judge: citations right", "citations"),
    ("Judge: admits gaps", "gaps"),
    ("Judge: question's language", "language"),
)


def summarize(paths: list[Path]) -> str:
    """A markdown table with a column per result file and a row per metric."""
    runs = [read_records(path) for path in paths]
    lines = [
        "| | " + " | ".join(f"{path.parent.name}/{path.stem}" for path in paths) + " |",
        "|---" * (len(paths) + 1) + "|",
        "| Run | " + " | ".join(_identity(run) for run in runs) + " |",
        "| Replies | " + " | ".join(str(len(run)) for run in runs) + " |",
    ]
    for label, field in METRICS:
        rates = (_share([r["score"][field] for r in run]) for run in runs)
        lines.append(f"| {label} | " + " | ".join(rates) + " |")

    judged = [_verdicts(path) for path in paths]
    if any(judged):
        judges = (
            f"{verdicts[0]['judge']}, rubric {verdicts[0].get('rubric', 'unrecorded')}"
            if verdicts
            else ""
            for verdicts in judged
        )
        lines.append("| Judged by | " + " | ".join(judges) + " |")
        for label, field in JUDGED:
            rates = (
                _share([v["verdict"][field] for v in verdicts if "verdict" in v])
                for verdicts in judged
            )
            lines.append(f"| {label} | " + " | ".join(rates) + " |")
    return "\n".join(lines)


def read_records(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def verdicts_file(results: Path) -> Path:
    """Where the judge files its verdicts on a run: beside it."""
    return results.with_suffix(".judge.jsonl")


def _verdicts(results: Path) -> list[dict]:
    path = verdicts_file(results)
    return read_records(path) if path.exists() else []


def _identity(run: list[dict]) -> str:
    if not run:
        return ""
    first = run[0]
    runtime = f", llama.cpp {first['runtime']}" if first["runtime"] else ""
    return f"{first['model']} on {first['target']}{runtime}"


def _share(values: list) -> str:
    counted = [bool(value) for value in values if value is not None]
    if not counted:
        return "n/a"
    met = sum(counted)
    return f"{100 * met / len(counted):.0f}% ({met}/{len(counted)})"
