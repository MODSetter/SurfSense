"""Shared fixtures for the ``app.automations`` unit-test tree.

Provides registry isolation: the built-in ``schedule`` trigger and
``agent_task`` action self-register at import time. Tests that register
additional triggers/actions (or assert on the registry contents) must
not leak that state to other tests. These fixtures snapshot and restore
the module-level registry dicts.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.automations.actions import store as action_store
from app.automations.triggers import store as trigger_store


@pytest.fixture
def isolated_action_registry() -> Iterator[None]:
    """Snapshot and restore the action registry around a test."""
    snapshot = dict(action_store._REGISTRY)
    try:
        yield
    finally:
        action_store._REGISTRY.clear()
        action_store._REGISTRY.update(snapshot)


@pytest.fixture
def isolated_trigger_registry() -> Iterator[None]:
    """Snapshot and restore the trigger registry around a test."""
    snapshot = dict(trigger_store._REGISTRY)
    try:
        yield
    finally:
        trigger_store._REGISTRY.clear()
        trigger_store._REGISTRY.update(snapshot)
