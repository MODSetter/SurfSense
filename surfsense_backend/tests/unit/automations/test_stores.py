"""Lock the trigger + action registry contracts.

Both stores share the same API shape (register/get/all + duplicate-raise),
so they're tested together to keep the contract visible side-by-side.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from app.automations.actions.store import (
    get_action,
    register_action,
)
from app.automations.actions.types import ActionDefinition
from app.automations.triggers.store import (
    all_triggers,
    get_trigger,
    register_trigger,
)
from app.automations.triggers.types import TriggerDefinition

pytestmark = pytest.mark.unit


class _Params(BaseModel):
    """Empty params model used by test-only registrations."""


def _trigger(type_: str = "test_trigger") -> TriggerDefinition:
    return TriggerDefinition(
        type=type_, description="Test trigger.", params_model=_Params
    )


def _action(type_: str = "test_action") -> ActionDefinition:
    return ActionDefinition(
        type=type_,
        name="Test",
        description="Test action.",
        params_model=_Params,
        build_handler=lambda _ctx: lambda _p: {},  # type: ignore[arg-type,return-value]
    )


def test_register_trigger_then_get_trigger_returns_the_same_definition(
    isolated_trigger_registry: None,
) -> None:
    """The canonical round-trip: register, look up by type, get the same
    definition back. Locks the basic registry contract."""
    definition = _trigger()
    register_trigger(definition)

    assert get_trigger("test_trigger") is definition


def test_register_action_then_get_action_returns_the_same_definition(
    isolated_action_registry: None,
) -> None:
    """Same round-trip contract for the action registry."""
    definition = _action()
    register_action(definition)

    assert get_action("test_action") is definition


def test_get_trigger_returns_none_for_unknown_type(
    isolated_trigger_registry: None,
) -> None:
    """An unknown type returns ``None`` (not raises). Lets callers like
    the dispatcher branch on "is this trigger still registered?" without
    try/except."""
    assert get_trigger("never_registered") is None


def test_get_action_returns_none_for_unknown_type(
    isolated_action_registry: None,
) -> None:
    """Same ``None``-not-raise contract on the action side."""
    assert get_action("never_registered") is None


def test_register_trigger_rejects_duplicate_type(
    isolated_trigger_registry: None,
) -> None:
    """Re-registering the same ``type`` raises rather than silently
    overwriting. Locks the safety net against accidental double-import
    (e.g., circular imports re-running the registration block)."""
    register_trigger(_trigger())

    with pytest.raises(ValueError, match="test_trigger"):
        register_trigger(_trigger())


def test_register_action_rejects_duplicate_type(
    isolated_action_registry: None,
) -> None:
    """Same duplicate-rejection contract on the action side."""
    register_action(_action())

    with pytest.raises(ValueError, match="test_action"):
        register_action(_action())


def test_all_triggers_returns_defensive_snapshot(
    isolated_trigger_registry: None,
) -> None:
    """``all_triggers()`` returns a copy: mutating the returned dict does
    not corrupt the internal registry. Locks the snapshot contract that
    UI/listing endpoints rely on."""
    register_trigger(_trigger("snapshot_test"))

    snapshot = all_triggers()
    snapshot.pop("snapshot_test")

    assert get_trigger("snapshot_test") is not None
