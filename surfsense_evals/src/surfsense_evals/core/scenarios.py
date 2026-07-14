"""Shared scenario formatting helpers for head-to-head benchmark reports.

The scenario chosen at ``setup`` time (``head-to-head``, ``symmetric-cheap``,
``cost-arbitrage``) materially changes how a head-to-head report should be
read. This module produces the one-bullet summary every head-to-head
runner stamps near the top of its ``report_section`` body so reviewers
immediately see the framing — no need to dig into ``run_artifact.json``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def format_scenario_md(extra: Mapping[str, Any] | None) -> str:
    """Render a scenario-aware bullet for a benchmark report.

    Reads ``extra["scenario"]`` plus the runtime LLM slugs the runner
    recorded. Falls back to a sensible "head-to-head" line if the artifact
    pre-dates scenarios so old runs still render cleanly.
    """

    extra = dict(extra or {})
    scenario = str(extra.get("scenario") or "head-to-head")
    surf_slug = str(extra.get("provider_model") or "?")
    native_slug = str(extra.get("native_arm_model") or surf_slug)
    vision_slug = extra.get("vision_provider_model")

    if scenario == "cost-arbitrage":
        body = (
            f"- Scenario: **cost-arbitrage** — native arm answers with "
            f"`{native_slug}` (vision); SurfSense answers with `{surf_slug}` "
            f"over chunks vision-extracted at ingest"
            f"{f' by `{vision_slug}`' if vision_slug else ''}. "
            "Measures how close SurfSense gets to native at a fraction of "
            "the per-query cost."
        )
    elif scenario == "symmetric-cheap":
        body = (
            f"- Scenario: **symmetric-cheap** — both arms answer with "
            f"`{surf_slug}`; SurfSense pre-extracted images at ingest"
            f"{f' via `{vision_slug}`' if vision_slug else ''}. "
            "Native arm structurally loses on image-bearing questions "
            "(text-only model can't see images) — that's the point."
        )
    else:
        body = f"- Scenario: head-to-head — both arms answer with `{surf_slug}` via OpenRouter."
        if vision_slug:
            body += f" SurfSense ingest VLM: `{vision_slug}`."

    return body


__all__ = ["format_scenario_md"]
