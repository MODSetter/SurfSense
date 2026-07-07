"""``Event`` contract: carry caller facts + engine-stamped id/time, round-trip JSON."""

from __future__ import annotations

from datetime import datetime

import pytest

from app.event_bus.event import Event

pytestmark = pytest.mark.unit


def test_event_carries_caller_supplied_facts() -> None:
    """The three caller inputs are stored verbatim."""
    event = Event(
        event_type="document.indexed",
        payload={"document_id": 42, "content_type": "pdf"},
        workspace_id=7,
    )

    assert event.event_type == "document.indexed"
    assert event.payload == {"document_id": 42, "content_type": "pdf"}
    assert event.workspace_id == 7


def test_event_stamps_identity_and_time_when_not_supplied() -> None:
    """Engine stamps id + time so subscribers can dedup/order."""
    event = Event(event_type="x.happened", payload={}, workspace_id=1)

    assert event.event_id
    assert isinstance(event.occurred_at, datetime)


def test_event_ids_are_unique_per_instance() -> None:
    """Two events published with identical content are still distinct facts."""
    first = Event(event_type="x.happened", payload={}, workspace_id=1)
    second = Event(event_type="x.happened", payload={}, workspace_id=1)

    assert first.event_id != second.event_id


def test_event_survives_json_round_trip() -> None:
    """Serialize → deserialize reproduces the event (subscribers queue it as JSON)."""
    original = Event(
        event_type="podcast.generated",
        payload={"podcast_id": 9, "duration_s": 123.5},
        workspace_id=3,
    )

    restored = Event.model_validate_json(original.model_dump_json())

    assert restored == original
