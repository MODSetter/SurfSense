"""An event hands its payload + metadata to the run as inputs."""

from __future__ import annotations

import pytest

from app.automations.triggers.builtin.event.inputs import event_runtime_inputs
from app.event_bus import Event

pytestmark = pytest.mark.unit


def test_runtime_inputs_flatten_payload_with_event_metadata() -> None:
    event = Event(
        event_type="document.indexed",
        payload={"document_id": 42, "document_type": "FILE"},
        workspace_id=7,
    )

    inputs = event_runtime_inputs(event)

    assert inputs["document_id"] == 42
    assert inputs["document_type"] == "FILE"
    assert inputs["event_type"] == "document.indexed"
    assert inputs["event_id"] == event.event_id
    assert inputs["occurred_at"] == event.occurred_at.isoformat()
