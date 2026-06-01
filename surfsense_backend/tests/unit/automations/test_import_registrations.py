"""Lock the bundled import side-effects.

Importing ``app.automations`` (the package) registers the v1 bundled
action (``agent_task``) and the v1 bundled trigger (``schedule``). If the
import chain breaks (e.g. someone removes ``from . import definition``
in a sub-package ``__init__``), the system would silently launch with an
empty registry. These tests are the canary.
"""

from __future__ import annotations

import pytest

import app.automations  # noqa: F401  (force the package import + its side-effects)
from app.automations.actions.store import get_action
from app.automations.persistence.enums.trigger_type import TriggerType
from app.automations.triggers.store import get_trigger

pytestmark = pytest.mark.unit


def test_bundled_agent_task_action_is_registered_after_package_import() -> None:
    """``agent_task`` — the v1 default action — must be discoverable in
    the registry after the package is imported."""
    definition = get_action("agent_task")

    assert definition is not None
    assert definition.type == "agent_task"


def test_bundled_schedule_trigger_is_registered_after_package_import() -> None:
    """``schedule`` — the only v1 trigger — must be discoverable in the
    registry after the package is imported."""
    definition = get_trigger(TriggerType.SCHEDULE.value)

    assert definition is not None
    assert definition.type == TriggerType.SCHEDULE.value
