"""Translate the unified langchain HITL envelope into permission-domain semantics.

``PermissionMiddleware`` works with the canonical shape
``{decision_type: "once" | "approve_always" | "reject", feedback?: str, edited_args?: dict}``.
The wire envelope arriving from langgraph already lives in the LC HITL shape
(parsed once in :mod:`hitl_wire.decision`); this module performs the small
domain mapping (``approve|edit`` → ``once``, ``approve_always`` →
``approve_always``, anything else → ``reject``) without re-implementing the
envelope walk.

Failing closed: any unrecognised decision becomes ``reject`` (with a warning)
so the middleware never proceeds on ambiguous input.
"""

from __future__ import annotations

import logging
from typing import Any

from app.agents.multi_agent_chat.subagents.shared.hitl.wire import (
    LC_DECISION_APPROVE,
    LC_DECISION_EDIT,
    LC_DECISION_REJECT,
    SURFSENSE_DECISION_APPROVE_ALWAYS,
    parse_lc_envelope,
)

logger = logging.getLogger(__name__)


# ``approve`` and ``edit`` both mean "let this call go through this once". The
# legacy SurfSense bare-scalar values (``once`` / ``approve_always`` / ``reject``)
# pass through unchanged so historical resume payloads still work.
_LC_TO_PERMISSION: dict[str, str] = {
    LC_DECISION_APPROVE: "once",
    LC_DECISION_EDIT: "once",
    SURFSENSE_DECISION_APPROVE_ALWAYS: "approve_always",
    LC_DECISION_REJECT: "reject",
    "once": "once",
    "approve_always": "approve_always",
    "reject": "reject",
}


def normalize_permission_decision(envelope: Any) -> dict[str, Any]:
    """Project the user's reply into the canonical permission decision shape.

    Args:
        envelope: The raw resume value from langgraph (LC HITL envelope, a
            bare scalar string, or a pre-canonical dict).

    Returns:
        ``{"decision_type": "once"|"approve_always"|"reject"}`` plus optional
        ``feedback`` (``reject`` with a user message) and ``edited_args``
        (``edit`` reply with non-empty arg overrides).
    """
    parsed = parse_lc_envelope(envelope)
    mapped = _LC_TO_PERMISSION.get(parsed.decision_type)
    if mapped is None:
        logger.warning(
            "Unknown permission decision %r; treating as reject",
            parsed.decision_type,
        )
        mapped = "reject"

    out: dict[str, Any] = {"decision_type": mapped}
    if parsed.message:
        out["feedback"] = parsed.message
    if parsed.edited_args:
        out["edited_args"] = parsed.edited_args
    return out


__all__ = ["normalize_permission_decision"]
