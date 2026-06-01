"""Lock the ``PlanStep`` validation contract."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.automations.schemas.definition.plan_step import PlanStep

pytestmark = pytest.mark.unit


def test_plan_step_accepts_minimal_input_with_safe_defaults() -> None:
    """A step with just ``step_id`` + ``action`` is valid. Defaults
    (no when, empty params, no output_as override, no retry/timeout
    override) let the run inherit automation-wide defaults."""
    step = PlanStep(step_id="s1", action="agent_task")

    assert step.step_id == "s1"
    assert step.action == "agent_task"
    assert step.when is None
    assert step.params == {}
    assert step.output_as is None
    assert step.max_retries is None
    assert step.timeout_seconds is None


def test_plan_step_rejects_empty_step_id_and_action() -> None:
    """``step_id`` and ``action`` are addressing primitives — empty
    strings would silently break runtime lookups."""
    with pytest.raises(ValidationError):
        PlanStep(step_id="", action="agent_task")
    with pytest.raises(ValidationError):
        PlanStep(step_id="s1", action="")


def test_plan_step_rejects_negative_max_retries_and_non_positive_timeout() -> None:
    """Numeric constraints: ``max_retries >= 0`` and ``timeout_seconds > 0``.
    Negative budgets or zero timeouts produce nonsensical run behavior."""
    with pytest.raises(ValidationError):
        PlanStep(step_id="s1", action="agent_task", max_retries=-1)
    with pytest.raises(ValidationError):
        PlanStep(step_id="s1", action="agent_task", timeout_seconds=0)


def test_plan_step_rejects_unknown_field() -> None:
    """``extra='forbid'`` catches typos like ``actoin`` (instead of
    ``action``) before the bad step reaches storage."""
    with pytest.raises(ValidationError):
        PlanStep.model_validate(
            {"step_id": "s1", "action": "agent_task", "actoin": "agent_task"}
        )
