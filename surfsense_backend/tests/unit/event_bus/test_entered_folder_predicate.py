"""payload_if_entered_folder: decides whether a document commit warrants an event."""

from __future__ import annotations

from typing import Any

import pytest

from app.event_bus.events.document_entered_folder import payload_if_entered_folder

pytestmark = pytest.mark.unit


def _call(**overrides: Any) -> dict[str, Any] | None:
    defaults: dict[str, Any] = {
        "document_id": 1,
        "workspace_id": 10,
        "new_folder_id": 7,
        "previous_folder_id": None,
        "folder_id_changed": True,
        "status_state": "ready",
        "document_type": "FILE",
        "title": "report.pdf",
        "connector_id": None,
        "created_by_id": None,
    }
    defaults.update(overrides)
    return payload_if_entered_folder(**defaults)


def test_folder_set_ready_fires() -> None:
    result = _call()

    assert result is not None
    assert result["event_type"] == "document.entered_folder"
    assert result["workspace_id"] == 10
    assert result["payload"]["folder_id"] == 7
    assert result["payload"]["previous_folder_id"] is None


def test_no_folder_is_silent() -> None:
    assert _call(new_folder_id=None) is None


def test_not_ready_is_silent() -> None:
    assert _call(status_state="processing") is None


def test_folder_unchanged_is_silent() -> None:
    assert _call(folder_id_changed=False) is None


def test_move_carries_previous_folder_id() -> None:
    result = _call(previous_folder_id=3, new_folder_id=7)

    assert result is not None
    assert result["payload"]["previous_folder_id"] == 3
    assert result["payload"]["folder_id"] == 7
