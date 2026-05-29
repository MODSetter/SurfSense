"""Lock creation-time model-policy enforcement in ``AutomationService``.

Creation (REST + manual builder) rejects search spaces whose models aren't
billable for automations with HTTP 422, mirroring the runtime backstop. These
tests isolate the new ``_assert_models_billable`` / ``model_eligibility`` paths
without touching the DB commit.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

import app.automations.services.automation as automation_mod
from app.automations.schemas.api import AutomationCreate, AutomationUpdate
from app.automations.schemas.definition.envelope import AutomationDefinition
from app.automations.schemas.definition.plan_step import PlanStep
from app.automations.services.automation import AutomationService
from app.automations.services.model_policy import AutomationModelPolicyError

pytestmark = pytest.mark.unit


class _FakeSession:
    def __init__(self, search_space: Any) -> None:
        self._search_space = search_space
        self.added: list[Any] = []
        self.commits = 0

    async def get(self, _model: Any, _pk: int) -> Any:
        return self._search_space

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.commits += 1


def _service(search_space: Any) -> AutomationService:
    return AutomationService(
        session=_FakeSession(search_space), user=SimpleNamespace(id="u-1")
    )


def _definition(**kwargs: Any) -> AutomationDefinition:
    return AutomationDefinition(
        name="A",
        plan=[PlanStep(step_id="s1", action="agent_task")],
        **kwargs,
    )


async def test_assert_models_billable_raises_422_on_violation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A blocked model maps the policy error to HTTP 422."""

    def _raise(_ss):
        raise AutomationModelPolicyError(
            [{"kind": "llm", "config_id": 0, "reason": "Auto mode"}]
        )

    monkeypatch.setattr(automation_mod, "assert_automation_models_billable", _raise)

    service = _service(SimpleNamespace(agent_llm_id=0))
    with pytest.raises(HTTPException) as exc_info:
        await service._assert_models_billable(1)

    assert exc_info.value.status_code == 422


async def test_assert_models_billable_raises_404_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing search space is a 404, not a policy error."""
    monkeypatch.setattr(
        automation_mod, "assert_automation_models_billable", lambda _ss: None
    )

    service = _service(None)
    with pytest.raises(HTTPException) as exc_info:
        await service._assert_models_billable(999)

    assert exc_info.value.status_code == 404


async def test_assert_models_billable_returns_search_space_when_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the policy accepts, the loaded search space is returned for reuse."""
    monkeypatch.setattr(
        automation_mod, "assert_automation_models_billable", lambda _ss: None
    )

    search_space = SimpleNamespace(agent_llm_id=-1)
    service = _service(search_space)
    assert await service._assert_models_billable(1) is search_space


async def test_create_injects_captured_models_from_search_space(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """create() snapshots the search space's model prefs onto the definition."""
    monkeypatch.setattr(
        automation_mod, "assert_automation_models_billable", lambda _ss: None
    )

    async def _noop_authorize(self, *_a, **_k):
        return None

    monkeypatch.setattr(AutomationService, "_authorize", _noop_authorize)

    async def _return_added(self, _aid):
        return self.session.added[-1]

    monkeypatch.setattr(AutomationService, "_get_with_triggers_or_raise", _return_added)

    search_space = SimpleNamespace(
        agent_llm_id=-1,
        image_generation_config_id=5,
        vision_llm_config_id=-1,
    )
    service = _service(search_space)
    payload = AutomationCreate(
        search_space_id=1,
        name="A",
        definition=_definition(),
    )

    automation = await service.create(payload)

    assert automation.definition["models"] == {
        "agent_llm_id": -1,
        "image_generation_config_id": 5,
        "vision_llm_config_id": -1,
    }


async def test_create_treats_unset_prefs_as_auto_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``None`` search-space prefs are captured as ``0`` (Auto) ids."""
    monkeypatch.setattr(
        automation_mod, "assert_automation_models_billable", lambda _ss: None
    )

    async def _noop_authorize(self, *_a, **_k):
        return None

    monkeypatch.setattr(AutomationService, "_authorize", _noop_authorize)

    async def _return_added(self, _aid):
        return self.session.added[-1]

    monkeypatch.setattr(AutomationService, "_get_with_triggers_or_raise", _return_added)

    search_space = SimpleNamespace(
        agent_llm_id=None,
        image_generation_config_id=None,
        vision_llm_config_id=None,
    )
    service = _service(search_space)
    payload = AutomationCreate(search_space_id=1, name="A", definition=_definition())

    automation = await service.create(payload)

    assert automation.definition["models"] == {
        "agent_llm_id": 0,
        "image_generation_config_id": 0,
        "vision_llm_config_id": 0,
    }


async def test_update_preserves_captured_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A definition edit carries over the previously captured ``models``."""
    captured = {
        "agent_llm_id": -1,
        "image_generation_config_id": 5,
        "vision_llm_config_id": -1,
    }
    existing = SimpleNamespace(
        search_space_id=1,
        definition={"name": "A", "plan": [], "models": captured},
        version=3,
    )

    async def _noop_authorize(self, *_a, **_k):
        return None

    async def _return_existing(self, _aid):
        return existing

    monkeypatch.setattr(AutomationService, "_authorize", _noop_authorize)
    monkeypatch.setattr(
        AutomationService, "_get_with_triggers_or_raise", _return_existing
    )

    service = _service(SimpleNamespace())
    # The incoming patch definition has no ``models`` (frontend strips it).
    patch = AutomationUpdate(definition=_definition())

    result = await service.update(7, patch)

    assert result.definition["models"] == captured
    assert result.version == 4


async def test_model_eligibility_authorizes_and_returns_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``model_eligibility`` checks read access then returns the eligibility dict."""
    authorized: dict[str, Any] = {}

    async def _fake_check_permission(_session, _user, ss_id, permission, _msg):
        authorized["search_space_id"] = ss_id
        authorized["permission"] = permission

    monkeypatch.setattr(automation_mod, "check_permission", _fake_check_permission)
    monkeypatch.setattr(
        automation_mod,
        "get_automation_model_eligibility",
        lambda _ss: {"allowed": False, "violations": [{"kind": "image"}]},
    )

    service = _service(SimpleNamespace(agent_llm_id=-2))
    result = await service.model_eligibility(search_space_id=5)

    assert result == {"allowed": False, "violations": [{"kind": "image"}]}
    assert authorized["search_space_id"] == 5
    assert authorized["permission"] == "automations:read"
