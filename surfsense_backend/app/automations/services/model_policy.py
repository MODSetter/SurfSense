"""Model-billing policy for automations.

Automations run unattended, so every run must be **billable**: it may only use
either a premium global model (``billing_tier == "premium"``) or a user-provided
BYOK model (a positive config id pointing at a per-user/per-space DB row). Free
global models and Auto mode are blocked, because Auto can dispatch to a free
deployment and free models aren't metered in premium credits.

Config id conventions (shared across chat / image / vision):
- ``id == 0``  → Auto mode (``AUTO_MODE_ID`` / ``IMAGE_GEN_AUTO_MODE_ID`` /
  ``VISION_AUTO_MODE_ID``). Blocked.
- ``id < 0``   → global YAML/OpenRouter config. Allowed only if premium.
- ``id > 0``   → user BYOK DB row. Always allowed.

This module is the single source of truth used by both creation-time enforcement
(``AutomationService.create`` and the ``create_automation`` chat tool) and the
runtime backstop (``agent_task`` dependencies).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from app.db import SearchSpace

ModelKind = Literal["llm", "image", "vision"]

_KIND_LABEL: dict[ModelKind, str] = {
    "llm": "agent LLM",
    "image": "image generation model",
    "vision": "vision model",
}


def _is_premium_global(kind: ModelKind, config_id: int) -> bool:
    """Return True if a negative (global) config id is a premium tier model."""
    from app.config import config as app_config

    cfg: dict | None = None
    if kind == "llm":
        from app.agents.shared.llm_config import load_global_llm_config_by_id

        cfg = load_global_llm_config_by_id(config_id)
    elif kind == "image":
        cfg = next(
            (
                c
                for c in app_config.GLOBAL_IMAGE_GEN_CONFIGS
                if c.get("id") == config_id
            ),
            None,
        )
    else:  # vision
        cfg = next(
            (
                c
                for c in app_config.GLOBAL_VISION_LLM_CONFIGS
                if c.get("id") == config_id
            ),
            None,
        )

    if not cfg:
        return False
    return str(cfg.get("billing_tier", "free")).lower() == "premium"


def _classify(kind: ModelKind, config_id: int | None) -> tuple[bool, str]:
    """Classify a resolved config id as allowed or blocked.

    Returns ``(allowed, reason)``; ``reason`` is empty when allowed.
    """
    label = _KIND_LABEL[kind]

    if config_id is None or config_id == 0:
        return (
            False,
            f"The {label} is set to Auto mode. Automations require an explicit "
            "premium model or your own (BYOK) model so every run is billable.",
        )

    if config_id > 0:
        # Positive id → user-owned BYOK config. Always allowed.
        return True, ""

    # Negative id → global config. Allowed only if premium.
    if _is_premium_global(kind, config_id):
        return True, ""

    return (
        False,
        f"The {label} is a free model. Automations can only use premium models "
        "or your own (BYOK) models so every run is billable.",
    )


def get_model_eligibility(
    *,
    agent_llm_id: int | None,
    image_generation_config_id: int | None,
    vision_llm_config_id: int | None,
) -> dict:
    """Return ``{"allowed": bool, "violations": [...]}`` for explicit config ids.

    The ID-based core shared by both the search-space path (creation/eligibility)
    and the captured-snapshot path (runtime backstop). Each violation is
    ``{"kind", "config_id", "reason"}``.
    """
    checks: list[tuple[ModelKind, int | None]] = [
        ("llm", agent_llm_id),
        ("image", image_generation_config_id),
        ("vision", vision_llm_config_id),
    ]

    violations: list[dict] = []
    for kind, config_id in checks:
        allowed, reason = _classify(kind, config_id)
        if not allowed:
            violations.append({"kind": kind, "config_id": config_id, "reason": reason})

    return {"allowed": not violations, "violations": violations}


def get_automation_model_eligibility(search_space: SearchSpace) -> dict:
    """Return ``{"allowed": bool, "violations": [...]}`` for a search space.

    Used by the eligibility endpoint and the chat tool's early check. Thin
    wrapper over :func:`get_model_eligibility`.
    """
    return get_model_eligibility(
        agent_llm_id=search_space.agent_llm_id,
        image_generation_config_id=search_space.image_generation_config_id,
        vision_llm_config_id=search_space.vision_llm_config_id,
    )


class AutomationModelPolicyError(Exception):
    """Raised when a search space's models are not billable for automations."""

    def __init__(self, violations: list[dict]) -> None:
        self.violations = violations
        reasons = "; ".join(v["reason"] for v in violations)
        super().__init__(
            reasons or "Automations require premium or BYOK models for all model slots."
        )


def assert_models_billable(
    *,
    agent_llm_id: int | None,
    image_generation_config_id: int | None,
    vision_llm_config_id: int | None,
) -> None:
    """Raise :class:`AutomationModelPolicyError` if any explicit id is not billable.

    The ID-based core used by the runtime backstop against an automation's
    captured model snapshot.
    """
    result = get_model_eligibility(
        agent_llm_id=agent_llm_id,
        image_generation_config_id=image_generation_config_id,
        vision_llm_config_id=vision_llm_config_id,
    )
    if not result["allowed"]:
        raise AutomationModelPolicyError(result["violations"])


def assert_automation_models_billable(search_space: SearchSpace) -> None:
    """Raise :class:`AutomationModelPolicyError` if any model slot is not billable."""
    result = get_automation_model_eligibility(search_space)
    if not result["allowed"]:
        raise AutomationModelPolicyError(result["violations"])
