"""Coerce inbound permission decisions to a canonical dict shape.

Two wire formats are accepted:
- SurfSense legacy: ``{"decision_type": "once"|"always"|"reject", "feedback"?}``.
- LangChain HITL envelope: ``{"decisions": [{"type": "approve"|"edit"|"reject", ...}]}``.

The middleware downstream only inspects the canonical shape returned here,
so adding a new envelope means changing this module alone.

The middleware fails closed: any unrecognised payload becomes ``reject``
(with a warning) so the agent never proceeds on ambiguous input.

When the reply is an ``edit``, the result keeps ``decision_type="once"``
(the call still goes through) and adds an ``edited_args`` key holding the
user-modified ``args`` dict. The orchestrator merges those into the
``tool_call`` before keeping it; see :mod:`interrupt.edit.merge`.
"""

from __future__ import annotations

import logging
from typing import Any

from .interrupt.edit import extract_edited_args

logger = logging.getLogger(__name__)


# ``edit`` collapses to ``once``; any ``edited_args`` ride on the result.
_LC_TYPE_TO_PERMISSION_DECISION: dict[str, str] = {
    "approve": "once",
    "reject": "reject",
    "edit": "once",
}


def normalize_permission_decision(decision: Any) -> dict[str, Any]:
    """Return ``{"decision_type": ..., "feedback"?: str, "edited_args"?: dict}``."""
    if isinstance(decision, str):
        return {"decision_type": decision}
    if not isinstance(decision, dict):
        logger.warning(
            "Unrecognized permission resume value (%s); treating as reject",
            type(decision).__name__,
        )
        return {"decision_type": "reject"}

    if decision.get("decision_type"):
        return decision

    payload: dict[str, Any] = decision
    decisions = decision.get("decisions")
    if isinstance(decisions, list) and decisions:
        first = decisions[0]
        if isinstance(first, dict):
            payload = first

    raw_type = payload.get("type") or payload.get("decision_type")
    if not raw_type:
        logger.warning(
            "Permission resume missing decision type (keys=%s); treating as reject",
            list(payload.keys()),
        )
        return {"decision_type": "reject"}

    raw_type = str(raw_type).lower()
    mapped = _LC_TYPE_TO_PERMISSION_DECISION.get(raw_type)
    if mapped is None:
        # Tolerate legacy values arriving without ``decision_type`` wrapping.
        if raw_type in {"once", "always", "reject"}:
            mapped = raw_type
        else:
            logger.warning(
                "Unknown permission decision type %r; treating as reject", raw_type
            )
            mapped = "reject"

    out: dict[str, Any] = {"decision_type": mapped}
    feedback = payload.get("feedback") or payload.get("message")
    if isinstance(feedback, str) and feedback.strip():
        out["feedback"] = feedback

    if raw_type == "edit":
        edited = extract_edited_args(payload)
        if edited:
            out["edited_args"] = edited

    return out


__all__ = ["normalize_permission_decision"]
