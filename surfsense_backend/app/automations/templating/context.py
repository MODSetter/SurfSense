"""Builder for the ``{run, inputs, steps}`` namespace exposed to every template."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any


def build_run_context(
    *,
    run_id: int,
    automation_id: int,
    automation_name: str | None,
    automation_version: int | None,
    workspace_id: int | None,
    creator_id: Any,
    trigger_id: int | None,
    trigger_type: str | None,
    started_at: datetime | None,
    attempt: int,
    inputs: Mapping[str, Any],
    step_outputs: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the ``{run, inputs, steps}`` namespace exposed to every template."""
    return {
        "run": {
            "id": run_id,
            "automation_id": automation_id,
            "automation_name": automation_name,
            "automation_version": automation_version,
            "workspace_id": workspace_id,
            "creator_id": creator_id,
            "trigger_id": trigger_id,
            "trigger_type": trigger_type,
            "started_at": started_at,
            "attempt": attempt,
        },
        "inputs": dict(inputs),
        "steps": dict(step_outputs),
    }
