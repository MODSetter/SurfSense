"""Model-billing policy for automations.

Automations run unattended, so every run must be **billable**: it may only use
either a premium global model (``billing_tier == "premium"``) or a user-provided
BYOK model (a positive model id pointing at a per-user/per-space DB row). Free
global models and Auto mode are blocked, because Auto can dispatch to a free
deployment and free models aren't metered in premium credits.

Model id conventions (shared across chat / image / vision):
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
    from app.db import Workspace

ModelKind = Literal["chat", "image", "vision"]

_KIND_LABEL: dict[ModelKind, str] = {
    "chat": "chat model",
    "image": "image generation model",
    "vision": "vision model",
}


def _is_premium_global(model_id: int) -> bool:
    """Return True if a negative (global) model id is a premium tier model."""
    from app.config import config as app_config

    model = next((m for m in app_config.GLOBAL_MODELS if m.get("id") == model_id), None)
    if not model:
        return False
    return str(model.get("billing_tier", "free")).lower() == "premium"


def _classify(kind: ModelKind, model_id: int | None) -> tuple[bool, str]:
    """Classify a resolved model id as allowed or blocked.

    Returns ``(allowed, reason)``; ``reason`` is empty when allowed.
    """
    label = _KIND_LABEL[kind]

    if model_id is None or model_id == 0:
        return (
            False,
            f"The {label} is set to Auto mode. Automations require an explicit "
            "premium model or your own (BYOK) model so every run is billable.",
        )

    if model_id > 0:
        # Positive id -> user/workspace BYOK model. Always allowed.
        return True, ""

    # Negative id -> global model. Allowed only if premium.
    if _is_premium_global(model_id):
        return True, ""

    return (
        False,
        f"The {label} is a free model. Automations can only use premium models "
        "or your own (BYOK) models so every run is billable.",
    )


def get_model_eligibility(
    *,
    chat_model_id: int | None,
    image_gen_model_id: int | None,
    vision_model_id: int | None,
) -> dict:
    """Return ``{"allowed": bool, "violations": [...]}`` for explicit model ids.

    The ID-based core shared by both the workspace path (creation/eligibility)
    and the captured-snapshot path (runtime backstop). Each violation is
    ``{"kind", "model_id", "reason"}``.
    """
    checks: list[tuple[ModelKind, int | None]] = [
        ("chat", chat_model_id),
        ("image", image_gen_model_id),
        ("vision", vision_model_id),
    ]

    violations: list[dict] = []
    for kind, model_id in checks:
        allowed, reason = _classify(kind, model_id)
        if not allowed:
            violations.append({"kind": kind, "model_id": model_id, "reason": reason})

    return {"allowed": not violations, "violations": violations}


def get_automation_model_eligibility(workspace: Workspace) -> dict:
    """Return ``{"allowed": bool, "violations": [...]}`` for a workspace.

    Used by the eligibility endpoint and the chat tool's early check. Thin
    wrapper over :func:`get_model_eligibility`.
    """
    return get_model_eligibility(
        chat_model_id=workspace.chat_model_id,
        image_gen_model_id=workspace.image_gen_model_id,
        vision_model_id=workspace.vision_model_id,
    )


class AutomationModelPolicyError(Exception):
    """Raised when a workspace's models are not billable for automations."""

    def __init__(self, violations: list[dict]) -> None:
        self.violations = violations
        reasons = "; ".join(v["reason"] for v in violations)
        super().__init__(
            reasons or "Automations require premium or BYOK models for all model slots."
        )


def assert_models_billable(
    *,
    chat_model_id: int | None,
    image_gen_model_id: int | None,
    vision_model_id: int | None,
) -> None:
    """Raise :class:`AutomationModelPolicyError` if any explicit id is not billable.

    The ID-based core used by the runtime backstop against an automation's
    captured model snapshot.
    """
    result = get_model_eligibility(
        chat_model_id=chat_model_id,
        image_gen_model_id=image_gen_model_id,
        vision_model_id=vision_model_id,
    )
    if not result["allowed"]:
        raise AutomationModelPolicyError(result["violations"])


def assert_automation_models_billable(workspace: Workspace) -> None:
    """Raise :class:`AutomationModelPolicyError` if any model slot is not billable."""
    result = get_automation_model_eligibility(workspace)
    if not result["allowed"]:
        raise AutomationModelPolicyError(result["violations"])
