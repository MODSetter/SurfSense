"""Lock the ``AutomationDefinition`` envelope contract."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.automations.schemas.definition.envelope import (
    AutomationDefinition,
    AutomationModels,
)
from app.automations.schemas.definition.plan_step import PlanStep

pytestmark = pytest.mark.unit


def test_automation_definition_accepts_minimal_valid_input_with_sensible_defaults() -> (
    None
):
    """A definition with just ``name`` + a one-step ``plan`` is valid and
    fills in the rest with safe defaults so users don't have to write
    out every section to get started."""
    definition = AutomationDefinition(
        name="Daily digest",
        plan=[PlanStep(step_id="s1", action="agent_task")],
    )

    assert definition.name == "Daily digest"
    assert definition.schema_version == "1.0"
    assert definition.goal is None
    assert definition.inputs is None
    assert definition.triggers == []
    # ``models`` is optional (populated server-side at create()).
    assert definition.models is None


def test_automation_definition_models_round_trip() -> None:
    """The captured ``models`` snapshot survives a model_dump/validate round-trip."""
    definition = AutomationDefinition(
        name="Daily digest",
        plan=[PlanStep(step_id="s1", action="agent_task")],
        models=AutomationModels(
            agent_llm_id=-1,
            image_generation_config_id=5,
            vision_llm_config_id=-1,
        ),
    )

    dumped = definition.model_dump(mode="json", by_alias=True)
    assert dumped["models"] == {
        "agent_llm_id": -1,
        "image_generation_config_id": 5,
        "vision_llm_config_id": -1,
    }

    restored = AutomationDefinition.model_validate(dumped)
    assert restored.models is not None
    assert restored.models.agent_llm_id == -1
    assert restored.models.image_generation_config_id == 5
    assert restored.models.vision_llm_config_id == -1


def test_automation_definition_rejects_unknown_top_level_field() -> None:
    """``extra='forbid'`` catches typos at validation time (e.g. ``pln``
    instead of ``plan``) before the bad definition reaches storage."""
    with pytest.raises(ValidationError):
        AutomationDefinition.model_validate(
            {
                "name": "X",
                "plan": [{"step_id": "s1", "action": "agent_task"}],
                "extra_field": "unexpected",
            }
        )


def test_automation_definition_rejects_empty_plan() -> None:
    """An automation with no plan steps has nothing to execute and must
    be rejected at validation time."""
    with pytest.raises(ValidationError):
        AutomationDefinition(name="X", plan=[])


def test_automation_definition_rejects_empty_name() -> None:
    """Name is required and must be non-empty so list views and audit
    logs have something meaningful to display."""
    with pytest.raises(ValidationError):
        AutomationDefinition(
            name="",
            plan=[PlanStep(step_id="s1", action="agent_task")],
        )
