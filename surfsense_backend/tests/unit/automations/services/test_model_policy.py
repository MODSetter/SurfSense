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


def _search_space(*, llm: int | None, image: int | None, vision: int | None):
    """Minimal stand-in for the ``SearchSpace`` ORM row the policy reads."""
    return SimpleNamespace(
        agent_llm_id=llm,
        image_generation_config_id=image,
        vision_llm_config_id=vision,
    )


@pytest.fixture
def patched_globals(monkeypatch: pytest.MonkeyPatch):
    """Stub the global config sources the policy consults for negative ids.

    Negative ids: -1 is premium, -2 is free, for each of llm/image/vision.
    """
    llm_configs = {
        -1: {"id": -1, "billing_tier": "premium"},
        -2: {"id": -2, "billing_tier": "free"},
    }
    monkeypatch.setattr(
        "app.agents.multi_agent_chat.shared.llm_config.load_global_llm_config_by_id",
        lambda cid: llm_configs.get(cid),
    )

    from app.config import config as app_config

    monkeypatch.setattr(
        app_config,
        "GLOBAL_IMAGE_GEN_CONFIGS",
        [
            {"id": -1, "billing_tier": "premium"},
            {"id": -2, "billing_tier": "free"},
        ],
        raising=False,
    )
    monkeypatch.setattr(
        app_config,
        "GLOBAL_VISION_LLM_CONFIGS",
        [
            {"id": -1, "billing_tier": "premium"},
            {"id": -2, "billing_tier": "free"},
        ],
        raising=False,
    )
    return None


@pytest.mark.parametrize("kind", ["llm", "image", "vision"])
def test_byok_positive_id_is_allowed(kind: str, patched_globals) -> None:
    """A positive config id is a user-owned BYOK model — always billable."""
    allowed, reason = model_policy._classify(kind, 7)
    assert allowed is True
    assert reason == ""


@pytest.mark.parametrize("kind", ["llm", "image", "vision"])
@pytest.mark.parametrize("config_id", [0, None])
def test_auto_mode_is_blocked(kind: str, config_id, patched_globals) -> None:
    """Auto mode (id 0) and an unset slot (None) are blocked."""
    allowed, reason = model_policy._classify(kind, config_id)
    assert allowed is False
    assert "Auto mode" in reason


@pytest.mark.parametrize("kind", ["llm", "image", "vision"])
def test_premium_global_is_allowed(kind: str, patched_globals) -> None:
    """A negative (global) id with premium billing tier is allowed."""
    allowed, reason = model_policy._classify(kind, -1)
    assert allowed is True
    assert reason == ""


@pytest.mark.parametrize("kind", ["llm", "image", "vision"])
def test_free_global_is_blocked(kind: str, patched_globals) -> None:
    """A negative (global) id with a free billing tier is blocked."""
    allowed, reason = model_policy._classify(kind, -2)
    assert allowed is False
    assert "free model" in reason


@pytest.mark.parametrize("kind", ["llm", "image", "vision"])
def test_unknown_global_id_is_blocked(kind: str, patched_globals) -> None:
    """A negative id that resolves to no config is treated as not premium."""
    allowed, _ = model_policy._classify(kind, -999)
    assert allowed is False


def test_eligibility_all_billable(patched_globals) -> None:
    """Premium LLM + BYOK image + premium vision → allowed, no violations."""
    search_space = _search_space(llm=-1, image=5, vision=-1)
    result = get_automation_model_eligibility(search_space)
    assert result == {"allowed": True, "violations": []}


def test_eligibility_reports_each_violation(patched_globals) -> None:
    """A free LLM, Auto image, and free vision each produce a violation."""
    search_space = _search_space(llm=-2, image=0, vision=-2)
    result = get_automation_model_eligibility(search_space)

    assert result["allowed"] is False
    kinds = {v["kind"] for v in result["violations"]}
    assert kinds == {"llm", "image", "vision"}
    # config_id is echoed back for the UI / settings deep-link.
    by_kind = {v["kind"]: v["config_id"] for v in result["violations"]}
    assert by_kind == {"llm": -2, "image": 0, "vision": -2}


def test_assert_raises_with_violations(patched_globals) -> None:
    """``assert_automation_models_billable`` raises when any slot is blocked."""
    search_space = _search_space(llm=0, image=5, vision=-1)
    with pytest.raises(AutomationModelPolicyError) as exc_info:
        assert_automation_models_billable(search_space)

    assert len(exc_info.value.violations) == 1
    assert exc_info.value.violations[0]["kind"] == "llm"


def test_assert_passes_when_all_billable(patched_globals) -> None:
    """No exception when every slot is premium or BYOK."""
    search_space = _search_space(llm=3, image=-1, vision=4)
    assert assert_automation_models_billable(search_space) is None


# --- ID-based core (used by the runtime backstop against captured snapshots) ---


def test_get_model_eligibility_all_billable(patched_globals) -> None:
    """Premium LLM + BYOK image + premium vision (explicit ids) → allowed."""
    result = get_model_eligibility(
        agent_llm_id=-1, image_generation_config_id=5, vision_llm_config_id=-1
    )
    assert result == {"allowed": True, "violations": []}


def test_get_model_eligibility_reports_each_violation(patched_globals) -> None:
    """Free LLM, Auto image, free vision (explicit ids) each produce a violation."""
    result = get_model_eligibility(
        agent_llm_id=-2, image_generation_config_id=0, vision_llm_config_id=-2
    )
    assert result["allowed"] is False
    by_kind = {v["kind"]: v["config_id"] for v in result["violations"]}
    assert by_kind == {"llm": -2, "image": 0, "vision": -2}


def test_assert_models_billable_raises(patched_globals) -> None:
    """``assert_models_billable`` raises when any explicit id is blocked."""
    with pytest.raises(AutomationModelPolicyError) as exc_info:
        assert_models_billable(
            agent_llm_id=0, image_generation_config_id=5, vision_llm_config_id=-1
        )
    assert len(exc_info.value.violations) == 1
    assert exc_info.value.violations[0]["kind"] == "llm"


def test_assert_models_billable_passes(patched_globals) -> None:
    """No exception when every explicit id is premium or BYOK."""
    assert (
        assert_models_billable(
            agent_llm_id=3, image_generation_config_id=-1, vision_llm_config_id=4
        )
        is None
    )


def test_search_space_wrapper_delegates_to_core(patched_globals) -> None:
    """The search-space wrapper produces the same result as the ID core."""
    search_space = _search_space(llm=-2, image=0, vision=-2)
    assert get_automation_model_eligibility(search_space) == get_model_eligibility(
        agent_llm_id=-2, image_generation_config_id=0, vision_llm_config_id=-2
    )
