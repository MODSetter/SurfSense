"""Report writer — composes per-benchmark sections into one summary.

Output:

* ``reports/<suite>/<run-timestamp>/summary.md`` — human-readable.
  Bullet lists only (no tables) per project's coding-standards.
* ``reports/<suite>/<run-timestamp>/summary.json`` — same content as
  structured JSON for downstream tooling (CI dashboards, regressions).

Headline benchmarks come first in both outputs.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from ..config import Config
from ..registry import ReportSection


def write_report(
    *,
    config: Config,
    suite: str,
    sections: Iterable[ReportSection],
    run_timestamp: str,
) -> Path:
    """Write ``summary.md`` + ``summary.json``. Returns the path of the .md file."""

    sections_list = list(sections)
    sections_list.sort(key=lambda s: (not s.headline, s.title.lower()))

    out_dir = config.suite_reports_dir(suite) / run_timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    md_path = out_dir / "summary.md"
    json_path = out_dir / "summary.json"

    md_lines: list[str] = [
        f"# SurfSense evals — suite `{suite}`",
        "",
        f"- Run timestamp: `{run_timestamp}`",
        f"- Sections: {len(sections_list)}",
        "",
    ]
    headline = [s for s in sections_list if s.headline]
    secondary = [s for s in sections_list if not s.headline]
    if headline:
        md_lines.append("## Headline")
        md_lines.append("")
        for section in headline:
            md_lines.append(f"### {section.title}")
            md_lines.append("")
            md_lines.append(section.body_md.rstrip())
            md_lines.append("")
    if secondary:
        md_lines.append("## Secondary measurements")
        md_lines.append("")
        for section in secondary:
            md_lines.append(f"### {section.title}")
            md_lines.append("")
            md_lines.append(section.body_md.rstrip())
            md_lines.append("")

    md_path.write_text("\n".join(md_lines).rstrip() + "\n", encoding="utf-8")

    json_payload = {
        "suite": suite,
        "run_timestamp": run_timestamp,
        "sections": [
            {
                "title": s.title,
                "headline": s.headline,
                "body_md": s.body_md,
                "body_json": s.body_json,
            }
            for s in sections_list
        ],
    }
    json_path.write_text(
        json.dumps(json_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return md_path


__all__ = ["ReportSection", "write_report"]
