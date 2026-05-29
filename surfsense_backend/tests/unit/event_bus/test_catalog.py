"""EventCatalog contract: register, look up, snapshot, derive schema."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from app.event_bus.catalog import EventCatalog, EventType

pytestmark = pytest.mark.unit


class _SamplePayload(BaseModel):
    document_id: int


def _event_type(type_: str = "test.thing") -> EventType:
    return EventType(
        type=type_,
        description="A thing happened.",
        payload_model=_SamplePayload,
    )


def test_register_then_get_returns_the_event_type(isolated_event_catalog: None) -> None:
    from app.event_bus.catalog import catalog
    catalog.register(_event_type())

    assert catalog.get("test.thing") is not None
    assert catalog.get("test.thing").type == "test.thing"


def test_get_unknown_type_returns_none(isolated_event_catalog: None) -> None:
    from app.event_bus.catalog import catalog
    assert catalog.get("does.not.exist") is None


def test_register_duplicate_type_raises(isolated_event_catalog: None) -> None:
    """A type is a contract; registering it twice is a bug, not an override."""
    from app.event_bus.catalog import catalog
    catalog.register(_event_type())

    with pytest.raises(ValueError, match="already registered"):
        catalog.register(_event_type())


def test_all_is_a_defensive_snapshot(isolated_event_catalog: None) -> None:
    """Mutating the returned dict must not corrupt the registry."""
    from app.event_bus.catalog import catalog
    catalog.register(_event_type())

    snapshot = catalog.all()
    snapshot.clear()

    assert catalog.get("test.thing") is not None


def test_payload_schema_is_derived_from_the_payload_model() -> None:
    """The JSON Schema a UI/validator consumes comes from the payload model."""
    event_type = _event_type()

    assert event_type.payload_schema == _SamplePayload.model_json_schema()


def test_each_catalog_instance_has_its_own_registry() -> None:
    """Two EventCatalog instances are fully independent."""
    a = EventCatalog()
    b = EventCatalog()

    a.register(_event_type())

    assert a.get("test.thing") is not None
    assert b.get("test.thing") is None
