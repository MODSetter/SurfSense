"""Lock the request-side automation API schemas — the public validation gate."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.automations.schemas.api.automation import AutomationCreate, AutomationUpdate

pytestmark = pytest.mark.unit


_VALID_DEFINITION = {
    "name": "Test",
    "plan": [{"step_id": "s1", "action": "agent_task"}],
}


def test_automation_create_accepts_valid_minimal_payload() -> None:
    """Happy path: just workspace_id, name, and a valid definition.
    Triggers default to ``[]`` so users can attach them later."""
    payload = AutomationCreate.model_validate(
        {
            "workspace_id": 1,
            "name": "Daily digest",
            "definition": _VALID_DEFINITION,
        }
    )

    assert payload.name == "Daily digest"
    assert payload.description is None
    assert payload.triggers == []


def test_automation_create_cascades_validation_into_nested_definition() -> None:
    """A bad ``definition`` (e.g. empty plan) fails at the API boundary,
    not at the DB layer. Locks the cascade so corrupt definitions can't
    sneak through a misshapen wire payload."""
    with pytest.raises(ValidationError):
        AutomationCreate.model_validate(
            {
                "workspace_id": 1,
                "name": "Bad",
                "definition": {"name": "X", "plan": []},  # empty plan
            }
        )


def test_automation_create_rejects_unknown_top_level_field() -> None:
    """``extra='forbid'`` catches typos in API payloads at the boundary."""
    with pytest.raises(ValidationError):
        AutomationCreate.model_validate(
            {
                "workspace_id": 1,
                "name": "X",
                "definition": _VALID_DEFINITION,
                "owner": "tg",  # not allowed
            }
        )


def test_automation_create_rejects_empty_name() -> None:
    """Name is required and constrained to 1..200 chars."""
    with pytest.raises(ValidationError):
        AutomationCreate.model_validate(
            {
                "workspace_id": 1,
                "name": "",
                "definition": _VALID_DEFINITION,
            }
        )


def test_automation_update_accepts_partial_payload_with_no_fields() -> None:
    """All fields on ``AutomationUpdate`` are optional. An empty body is
    a valid no-op update (the service layer decides what to do with it)."""
    update = AutomationUpdate.model_validate({})

    assert update.name is None
    assert update.description is None
    assert update.status is None
    assert update.definition is None
