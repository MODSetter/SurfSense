"""Pure-logic unit tests for the chat watch service.

Only the deterministic, infra-free pieces live here: the plan predicate that
decides whether an automation watches a thread, and the schedule-trigger
picker. Everything that touches ``AutomationService``/Postgres (create, find,
stop, run-now) is proven against real infra in
``tests/integration/automations/services/test_chat_watch.py`` — faking the
service we own would only assert wiring and hide the model-billing gate,
RBAC, and JSON round-trip that those calls really go through.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.automations.persistence.enums.trigger_type import TriggerType
from app.automations.persistence.models.trigger import AutomationTrigger
from app.automations.services.chat_watch import (
    WATCH_ACTION_TYPE,
    plan_targets_thread,
    schedule_trigger,
)

pytestmark = pytest.mark.unit


def _definition_with_step(action: str, params: dict[str, Any]) -> dict[str, Any]:
    return {"plan": [{"step_id": "s", "action": action, "params": params}]}


def test_plan_targets_thread_true_for_matching_chat_message_step() -> None:
    definition = _definition_with_step("chat_message", {"thread_id": 55, "message": "x"})
    assert plan_targets_thread(definition, 55) is True
    assert WATCH_ACTION_TYPE == "chat_message"


def test_plan_targets_thread_false_for_other_thread_or_action() -> None:
    assert (
        plan_targets_thread(
            _definition_with_step("chat_message", {"thread_id": 999}), 55
        )
        is False
    )
    assert (
        plan_targets_thread(
            _definition_with_step("agent_task", {"thread_id": 55}), 55
        )
        is False
    )
    assert plan_targets_thread({}, 55) is False
    assert plan_targets_thread(None, 55) is False


class _Automation:
    """Minimal stand-in carrying only the ``triggers`` list the picker reads."""

    def __init__(self, triggers: list[AutomationTrigger]) -> None:
        self.triggers = triggers


def _trigger(type_: TriggerType) -> AutomationTrigger:
    return AutomationTrigger(type=type_, params={}, enabled=True)


def test_schedule_trigger_picks_the_schedule_row() -> None:
    schedule = _trigger(TriggerType.SCHEDULE)
    automation = _Automation([_trigger(TriggerType.EVENT), schedule])
    assert schedule_trigger(automation) is schedule


def test_schedule_trigger_returns_none_without_a_schedule() -> None:
    automation = _Automation([_trigger(TriggerType.EVENT)])
    assert schedule_trigger(automation) is None
