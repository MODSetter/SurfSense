"""A contract review as the agent tells it: what each review point came to, and the points a
person must take over, with why."""

from __future__ import annotations

from typing import Any

# Points named in the reply; the rest are in the run's report in Studio.
NAMED_POINTS = 12


def review_summary(artifact_id: int, report: dict[str, Any]) -> str:
    counts = report.get("counts") or {}
    lines = [
        f"Done: version 1 of a revised copy (artifact {artifact_id}) in Studio. Of "
        f"{report.get('points', 0)} review points, {counts.get('changed', 0)} were changed "
        f"with tracked changes, {counts.get('meets', 0)} meet the firm's playbook, "
        f"{counts.get('not_covered', 0)} are not covered by it and were left alone, and "
        f"{counts.get('for_person', 0)} are left to a person. Each change carries a comment; "
        "SurfSense's reasoning and the playbook quote it rests on are internal comments, "
        "which stay in Studio and are left out of every download."
    ]
    exceptions = report.get("exceptions") or []
    for where, _text, point, _said, why in exceptions[:NAMED_POINTS]:
        lines.append(f"- {point}{f' ({where})' if where else ''}: {why}")
    if len(exceptions) > NAMED_POINTS:
        lines.append(f"- and {len(exceptions) - NAMED_POINTS} more in Studio.")
    return "\n".join(lines)
