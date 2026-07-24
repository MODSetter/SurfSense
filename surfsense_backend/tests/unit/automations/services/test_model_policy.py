"""Lock the automation model-billing policy.

Automations may only run on billable models: premium global configs
(``billing_tier == "premium"``) or user BYOK configs (positive id). Free
globals and Auto mode (id == 0 / None) are blocked. These tests pin that rule
across all three model slots (chat LLM, image, vision).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.automations.services.model_policy as model_policy
from app.automations.services.model_policy import (
    AutomationModelPolicyError,
    assert_automation_models_billable,
    assert_models_billable,
    get_automation_model_eligibility,
    get_model_eligibility,
)

pytestmark = pytest.mark.unit


def _workspace(*, llm: int | None, image: int | None, vision: int | None):
    """Minimal stand-in for the ``Workspace`` ORM row the policy reads."""
    return SimpleNamespace(
        chat_model_id=llm,
        image_gen_model_id=image,
        vision_model_id=vision,
    )


@pytest.fixture
def patched_globals(monkeypatch: pytest.MonkeyPatch):
    """Stub the global config sources the policy consults for negative ids.

    Negative ids: -1 is premium, -2 is free, for each of llm/image/vision.
    """
    from app.config import config as app_config

    monkeypatch.setattr(
        app_config,
        "GLOBAL_MODELS",
        [
            {"id": -1, "billing_tier": "premium"},
            {"id": -2, "billing_tier": "free"},
        ],
        raising=False,
    )
    return None


@pytest.mark.parametrize("kind", ["chat", "image", "vision"])
def test_byok_positive_id_is_allowed(kind: str, patched_globals) -> None:
    """A positive config id is a user-owned BYOK model — always billable."""
    allowed, reason = model_policy._classify(kind, 7)
    assert allowed is True
    assert reason == ""


@pytest.mark.parametrize("kind", ["chat", "image", "vision"])
@pytest.mark.parametrize("config_id", [0, None])
def test_auto_mode_is_blocked(kind: str, config_id, patched_globals) -> None:
    """Auto mode (id 0) and an unset slot (None) are blocked."""
    allowed, reason = model_policy._classify(kind, config_id)
    assert allowed is False
    assert "Auto mode" in reason


@pytest.mark.parametrize("kind", ["chat", "image", "vision"])
def test_premium_global_is_allowed(kind: str, patched_globals) -> None:
    """A negative (global) id with premium billing tier is allowed."""
    allowed, reason = model_policy._classify(kind, -1)
    assert allowed is True
    assert reason == ""


@pytest.mark.parametrize("kind", ["chat", "image", "vision"])
def test_free_global_is_blocked(kind: str, patched_globals) -> None:
    """A negative (global) id with a free billing tier is blocked."""
    allowed, reason = model_policy._classify(kind, -2)
    assert allowed is False
    assert "free model" in reason


@pytest.mark.parametrize("kind", ["chat", "image", "vision"])
def test_unknown_global_id_is_blocked(kind: str, patched_globals) -> None:
    """A negative id that resolves to no config is treated as not premium."""
    allowed, _ = model_policy._classify(kind, -999)
    assert allowed is False


def test_eligibility_all_billable(patched_globals) -> None:
    """Premium LLM + BYOK image + premium vision → allowed, no violations."""
    workspace = _workspace(llm=-1, image=5, vision=-1)
    result = get_automation_model_eligibility(workspace)
    assert result == {"allowed": True, "violations": []}


def test_eligibility_reports_each_violation(patched_globals) -> None:
    """A free LLM, Auto image, and free vision each produce a violation."""
    workspace = _workspace(llm=-2, image=0, vision=-2)
    result = get_automation_model_eligibility(workspace)

    assert result["allowed"] is False
    kinds = {v["kind"] for v in result["violations"]}
    assert kinds == {"chat", "image", "vision"}
    # model_id is echoed back for the UI / settings deep-link.
    by_kind = {v["kind"]: v["model_id"] for v in result["violations"]}
    assert by_kind == {"chat": -2, "image": 0, "vision": -2}


def test_assert_raises_with_violations(patched_globals) -> None:
    """``assert_automation_models_billable`` raises when any slot is blocked."""
    workspace = _workspace(llm=0, image=5, vision=-1)
    with pytest.raises(AutomationModelPolicyError) as exc_info:
        assert_automation_models_billable(workspace)

    assert len(exc_info.value.violations) == 1
    assert exc_info.value.violations[0]["kind"] == "chat"


def test_assert_passes_when_all_billable(patched_globals) -> None:
    """No exception when every slot is premium or BYOK."""
    workspace = _workspace(llm=3, image=-1, vision=4)
    assert assert_automation_models_billable(workspace) is None


# --- ID-based core (used by the runtime backstop against captured snapshots) ---


def test_get_model_eligibility_all_billable(patched_globals) -> None:
    """Premium LLM + BYOK image + premium vision (explicit ids) → allowed."""
    result = get_model_eligibility(
        chat_model_id=-1, image_gen_model_id=5, vision_model_id=-1
    )
    assert result == {"allowed": True, "violations": []}


def test_get_model_eligibility_reports_each_violation(patched_globals) -> None:
    """Free LLM, Auto image, free vision (explicit ids) each produce a violation."""
    result = get_model_eligibility(
        chat_model_id=-2, image_gen_model_id=0, vision_model_id=-2
    )
    assert result["allowed"] is False
    by_kind = {v["kind"]: v["model_id"] for v in result["violations"]}
    assert by_kind == {"chat": -2, "image": 0, "vision": -2}


def test_assert_models_billable_raises(patched_globals) -> None:
    """``assert_models_billable`` raises when any explicit id is blocked."""
    with pytest.raises(AutomationModelPolicyError) as exc_info:
        assert_models_billable(
            chat_model_id=0, image_gen_model_id=5, vision_model_id=-1
        )
    assert len(exc_info.value.violations) == 1
    assert exc_info.value.violations[0]["kind"] == "chat"


def test_assert_models_billable_passes(patched_globals) -> None:
    """No exception when every explicit id is premium or BYOK."""
    assert (
        assert_models_billable(
            chat_model_id=3, image_gen_model_id=-1, vision_model_id=4
        )
        is None
    )


def test_workspace_wrapper_delegates_to_core(patched_globals) -> None:
    """The workspace wrapper produces the same result as the ID core."""
    workspace = _workspace(llm=-2, image=0, vision=-2)
    assert get_automation_model_eligibility(workspace) == get_model_eligibility(
        chat_model_id=-2, image_gen_model_id=0, vision_model_id=-2
    )
