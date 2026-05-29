"""``document.entered_folder`` payload contract + catalog registration."""

from __future__ import annotations

import pytest

from app.event_bus.catalog import catalog
from app.event_bus.events.document_entered_folder import (
    EVENT_TYPE,
    DocumentEnteredFolderPayload,
)

pytestmark = pytest.mark.unit


def _payload(**overrides: object) -> DocumentEnteredFolderPayload:
    base: dict[str, object] = {
        "document_id": 42,
        "folder_id": 7,
        "document_type": "FILE",
        "title": "Q3 report.pdf",
    }
    base.update(overrides)
    return DocumentEnteredFolderPayload(**base)


def test_payload_carries_the_filterable_fields() -> None:
    payload = _payload(connector_id=12, created_by_id="abc")

    assert payload.document_id == 42
    assert payload.folder_id == 7
    assert payload.document_type == "FILE"
    assert payload.connector_id == 12


def test_first_placement_is_not_a_move() -> None:
    """No previous folder (created or AI-sorted into place) → not a move."""
    assert _payload(previous_folder_id=None).is_move is False


def test_change_between_folders_is_a_move() -> None:
    assert _payload(previous_folder_id=3).is_move is True


def test_is_move_is_serialized_for_filtering() -> None:
    """Filters match against the dumped payload, so ``is_move`` must appear there."""
    dumped = _payload(previous_folder_id=3).model_dump()

    assert dumped["is_move"] is True


def test_event_type_is_registered_in_the_catalog() -> None:
    registered = catalog.get(EVENT_TYPE)

    assert registered is not None
    assert registered.payload_model is DocumentEnteredFolderPayload
