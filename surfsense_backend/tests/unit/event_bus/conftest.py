"""Shared fixtures for the ``app.event_bus`` unit-test tree.

The event-type catalog is a module-level registry populated at import. Tests
that register their own event types (or assert on registry contents) snapshot
and restore it so state never leaks between tests.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.event_bus.catalog import catalog


@pytest.fixture
def isolated_event_catalog() -> Iterator[None]:
    """Snapshot and restore the event-type catalog around a test."""
    snapshot = dict(catalog._registry)
    try:
        yield
    finally:
        catalog._registry.clear()
        catalog._registry.update(snapshot)
