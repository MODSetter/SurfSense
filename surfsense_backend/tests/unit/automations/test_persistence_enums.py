"""Lock the persistence enum string values + members.

These enums are mirrored by Postgres enum types, embedded in stored DB
rows, and surfaced in the JSON API. Renaming a value (or removing a
member) silently breaks production data and previously-issued API
responses, so the strings + the set of members are the contract.
"""

from __future__ import annotations

import pytest

from app.automations.persistence.enums.automation_status import AutomationStatus
from app.automations.persistence.enums.run_status import RunStatus
from app.automations.persistence.enums.trigger_type import TriggerType

pytestmark = pytest.mark.unit


def test_automation_status_string_values_are_stable() -> None:
    """The exact strings persisted to Postgres and served in API JSON."""
    assert {member.value for member in AutomationStatus} == {
        "active",
        "paused",
        "archived",
    }


def test_run_status_string_values_are_stable() -> None:
    """Run lifecycle states embedded in the ``automation_runs`` table."""
    assert {member.value for member in RunStatus} == {
        "pending",
        "running",
        "succeeded",
        "failed",
        "cancelled",
        "timed_out",
    }


def test_trigger_type_keeps_manual_member_even_though_unregistered() -> None:
    """``schedule`` and ``event`` are registered; ``MANUAL`` is reserved
    (mirrors the Postgres enum) but the trigger store does not register it.
    The enum must keep every member so DB rows and migrations stay valid."""
    assert {member.value for member in TriggerType} == {"schedule", "event", "manual"}
