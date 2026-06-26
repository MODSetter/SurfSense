"""Lock the runtime model-policy backstop in ``build_dependencies``.

Automations resolve their LLM from the *captured* ``chat_model_id`` snapshot (so
runs are insulated from later chat/workspace model changes), and the model
policy is re-checked at run time so a captured model that is no longer billable
fails the run clearly. When no snapshot is present, resolution falls back to the
live workspace.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import app.automations.actions.builtin.agent_task.dependencies as deps_mod
from app.automations.actions.builtin.agent_task.dependencies import (
    DependencyError,
    build_dependencies,
)
from app.automations.services.model_policy import AutomationModelPolicyError

pytestmark = pytest.mark.unit


class _FakeSession:
    """Minimal async session whose ``get`` returns a preset workspace."""

    def __init__(self, workspace: Any) -> None:
        self._workspace = workspace

    async def get(self, _model: Any, _pk: int) -> Any:
        return self._workspace


@pytest.fixture
def patched_side_effects(monkeypatch: pytest.MonkeyPatch):
    """Stub the connector setup + checkpointer so only policy/LLM logic runs."""

    async def _fake_setup(_session, *, workspace_id):
        return (SimpleNamespace(name="connector"), "fc-key")

    monkeypatch.setattr(deps_mod, "setup_connector_and_firecrawl", _fake_setup)
    return None


async def test_build_dependencies_resolves_captured_chat_model_id(
    monkeypatch: pytest.MonkeyPatch, patched_side_effects
) -> None:
    """The bundle loads with the *captured* ``chat_model_id``, not the live workspace."""
    captured: dict[str, Any] = {}

    async def _fake_load(_session, *, config_id, workspace_id):
        captured["config_id"] = config_id
        captured["workspace_id"] = workspace_id
        return (SimpleNamespace(name="llm"), SimpleNamespace(name="agent_config"), None)

    monkeypatch.setattr(deps_mod, "load_llm_bundle", _fake_load)
    # Captured path validates the explicit ids; passes for this test.
    monkeypatch.setattr(deps_mod, "assert_models_billable", lambda **_kw: None)
    # A different value on the live workspace proves we ignore it when a
    # snapshot is supplied.
    monkeypatch.setattr(
        deps_mod,
        "assert_automation_models_billable",
        lambda _ss: pytest.fail("workspace policy should not run on captured path"),
    )

    workspace = SimpleNamespace(chat_model_id=-99)
    result = await build_dependencies(
        session=_FakeSession(workspace),
        workspace_id=42,
        chat_model_id=-7,
        image_gen_model_id=5,
        vision_model_id=-1,
    )

    assert captured == {"config_id": -7, "workspace_id": 42}
    assert result.llm.name == "llm"
    assert result.firecrawl_api_key == "fc-key"


async def test_build_dependencies_validates_captured_ids(
    monkeypatch: pytest.MonkeyPatch, patched_side_effects
) -> None:
    """The captured ids (not the workspace) are what gets policy-checked."""
    seen: dict[str, Any] = {}

    def _capture(**kwargs):
        seen.update(kwargs)

    monkeypatch.setattr(deps_mod, "assert_models_billable", _capture)

    async def _fake_load(_session, *, config_id, workspace_id):
        return (SimpleNamespace(name="llm"), SimpleNamespace(name="agent_config"), None)

    monkeypatch.setattr(deps_mod, "load_llm_bundle", _fake_load)

    await build_dependencies(
        session=_FakeSession(SimpleNamespace(chat_model_id=0)),
        workspace_id=42,
        chat_model_id=-7,
        image_gen_model_id=5,
        vision_model_id=-1,
    )

    assert seen == {
        "chat_model_id": -7,
        "image_gen_model_id": 5,
        "vision_model_id": -1,
    }


async def test_build_dependencies_raises_on_captured_policy_violation(
    monkeypatch: pytest.MonkeyPatch, patched_side_effects
) -> None:
    """A blocked captured model raises ``DependencyError`` so the step fails clearly."""

    def _raise(**_kw):
        raise AutomationModelPolicyError(
            [{"kind": "image", "model_id": -2, "reason": "free model"}]
        )

    monkeypatch.setattr(deps_mod, "assert_models_billable", _raise)
    monkeypatch.setattr(
        deps_mod,
        "load_llm_bundle",
        lambda *a, **k: pytest.fail("load_llm_bundle should not be called"),
    )

    with pytest.raises(DependencyError):
        await build_dependencies(
            session=_FakeSession(SimpleNamespace(chat_model_id=-7)),
            workspace_id=42,
            chat_model_id=-7,
            image_gen_model_id=-2,
            vision_model_id=-1,
        )


async def test_build_dependencies_falls_back_to_workspace(
    monkeypatch: pytest.MonkeyPatch, patched_side_effects
) -> None:
    """With no captured snapshot, resolve + validate the live workspace."""
    captured: dict[str, Any] = {}

    async def _fake_load(_session, *, config_id, workspace_id):
        captured["config_id"] = config_id
        return (SimpleNamespace(name="llm"), SimpleNamespace(name="agent_config"), None)

    monkeypatch.setattr(deps_mod, "load_llm_bundle", _fake_load)
    monkeypatch.setattr(deps_mod, "assert_automation_models_billable", lambda _ss: None)
    monkeypatch.setattr(
        deps_mod,
        "assert_models_billable",
        lambda **_kw: pytest.fail("captured policy should not run on fallback path"),
    )

    workspace = SimpleNamespace(chat_model_id=-7)
    result = await build_dependencies(
        session=_FakeSession(workspace), workspace_id=42
    )

    assert captured == {"config_id": -7}
    assert result.llm.name == "llm"


async def test_build_dependencies_raises_when_workspace_missing(
    patched_side_effects,
) -> None:
    """A missing workspace (fallback path) surfaces as a ``DependencyError``."""
    with pytest.raises(DependencyError):
        await build_dependencies(session=_FakeSession(None), workspace_id=999)
