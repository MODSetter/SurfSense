"""Lock the ``{run, inputs, steps}`` namespace exposed to every template."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.automations.templating.context import build_run_context

pytestmark = pytest.mark.unit


def test_build_run_context_exposes_run_inputs_and_steps_namespaces() -> None:
    """The namespace handed to templates groups run metadata under ``run``,
    runtime + static inputs under ``inputs``, and step outputs (keyed by
    ``output_as`` / ``step_id``) under ``steps``. Locks the contract that
    every plan template body relies on."""
    creator = UUID("00000000-0000-0000-0000-000000000001")
    started = datetime(2026, 5, 28, 14, 30, tzinfo=UTC)

    ctx = build_run_context(
        run_id=42,
        automation_id=7,
        automation_name="Weekly digest",
        automation_version=3,
        workspace_id=1,
        creator_id=creator,
        trigger_id=11,
        trigger_type="schedule",
        started_at=started,
        attempt=2,
        inputs={"topic": "weekly"},
        step_outputs={"summarize": {"text": "ok"}},
    )

    assert ctx == {
        "run": {
            "id": 42,
            "automation_id": 7,
            "automation_name": "Weekly digest",
            "automation_version": 3,
            "workspace_id": 1,
            "creator_id": creator,
            "trigger_id": 11,
            "trigger_type": "schedule",
            "started_at": started,
            "attempt": 2,
        },
        "inputs": {"topic": "weekly"},
        "steps": {"summarize": {"text": "ok"}},
    }
