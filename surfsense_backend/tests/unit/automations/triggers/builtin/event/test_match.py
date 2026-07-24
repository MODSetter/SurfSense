"""Which triggers an event fires: event_type equality + filter match."""

from __future__ import annotations

import pytest

from app.automations.triggers.builtin.event.match import trigger_matches_event
from app.event_bus import Event

pytestmark = pytest.mark.unit


def _event(event_type: str = "document.indexed", **payload) -> Event:
    return Event(event_type=event_type, payload=payload, workspace_id=7)


def test_matches_when_event_type_equal_and_filter_passes() -> None:
    params = {"event_type": "document.indexed", "filter": {"document_type": "FILE"}}
    assert trigger_matches_event(params, _event(document_type="FILE")) is True


def test_no_match_when_event_type_differs() -> None:
    params = {"event_type": "document.indexed", "filter": {}}
    assert trigger_matches_event(params, _event("podcast.generated")) is False


def test_no_match_when_filter_rejects_payload() -> None:
    params = {"event_type": "document.indexed", "filter": {"document_type": "FILE"}}
    assert trigger_matches_event(params, _event(document_type="WEBPAGE")) is False


def test_empty_filter_matches_any_payload_of_that_type() -> None:
    params = {"event_type": "document.indexed", "filter": {}}
    assert trigger_matches_event(params, _event(document_type="ANYTHING")) is True


def test_missing_filter_key_is_treated_as_empty() -> None:
    params = {"event_type": "document.indexed"}
    assert trigger_matches_event(params, _event(document_type="X")) is True
