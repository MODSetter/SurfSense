"""``EventTriggerParams`` contract: an event_type to listen for + an optional filter."""

from __future__ import annotations

import pytest

from app.automations.triggers.builtin.event.params import EventTriggerParams

pytestmark = pytest.mark.unit


def test_accepts_event_type_and_filter() -> None:
    params = EventTriggerParams(
        event_type="document.indexed",
        filter={"document_type": "FILE"},
    )

    assert params.event_type == "document.indexed"
    assert params.filter == {"document_type": "FILE"}


def test_filter_defaults_to_empty() -> None:
    params = EventTriggerParams(event_type="document.indexed")

    assert params.filter == {}


def test_event_type_is_required() -> None:
    with pytest.raises(ValueError):
        EventTriggerParams(filter={"x": 1})


def test_event_type_must_not_be_blank() -> None:
    with pytest.raises(ValueError):
        EventTriggerParams(event_type="")


def test_extra_keys_are_forbidden() -> None:
    with pytest.raises(ValueError):
        EventTriggerParams(event_type="document.indexed", typo=True)
