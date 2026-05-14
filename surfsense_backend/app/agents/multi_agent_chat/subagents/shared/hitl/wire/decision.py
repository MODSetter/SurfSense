"""Parse the langchain HITL resume envelope into a typed decision.

Both self-gated approvals (``request_approval``) and middleware-gated paths
(``PermissionMiddleware``) receive the user's reply through langgraph's
``Command(resume=...)`` channel as ``{"decisions": [{"type": ..., ...}]}``.
This module owns the decoding so the wire-shape knowledge lives in exactly
one place; callers project the parsed values into their own domain decisions
(``HITLResult`` for self-gated, ``decision_type`` for permissions) without
re-implementing the envelope walk.

Failing closed: any unrecognized envelope shape collapses to
``decision_type="reject"`` (with a warning) so callers never proceed on
ambiguous input.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ParsedLcDecision:
    """Decoded resume reply with the fields callers actually need.

    Attributes:
        decision_type: Lower-cased decision identifier — ``"approve"``,
            ``"reject"``, ``"edit"``, ``"always"``, or any custom value the
            FE may emit. Callers map this to their own domain semantics.
        edited_args: Populated only on ``"edit"`` replies that actually carry
            args; ``None`` otherwise so callers can use truthiness directly.
        message: Free-form user feedback (typically attached to ``"reject"``).
            ``None`` when absent or when the value isn't a non-empty string.
    """

    decision_type: str
    edited_args: dict[str, Any] | None = None
    message: str | None = None


def parse_lc_envelope(envelope: Any) -> ParsedLcDecision:
    """Extract a typed decision from a langgraph resume envelope.

    Accepts:

    - ``{"decisions": [{"type": "approve" | "reject" | "edit", ...}]}`` — the
      langchain HITL standard envelope.
    - A bare scalar string (``"once"``, ``"always"``, ``"reject"``) — used by
      the legacy SurfSense permission wire. We tolerate it so the parser can
      sit behind both call sites without a second adapter.

    Edit args are read from the standard ``edited_action.args`` first, then
    fall back to a flat ``args`` field for legacy compatibility — both shapes
    are produced by the FE depending on which card variant was rendered.

    Args:
        envelope: The raw resume value as it arrived from langgraph.

    Returns:
        A :class:`ParsedLcDecision` describing the user's intent.
    """
    if isinstance(envelope, str):
        return ParsedLcDecision(decision_type=envelope.lower())

    if not isinstance(envelope, dict):
        logger.warning(
            "Resume envelope is not a dict (got %s); treating as reject",
            type(envelope).__name__,
        )
        return ParsedLcDecision(decision_type="reject")

    payload: dict[str, Any] = envelope
    decisions = envelope.get("decisions")
    if isinstance(decisions, list) and decisions:
        first = decisions[0]
        if isinstance(first, dict):
            payload = first

    raw_type = payload.get("type") or payload.get("decision_type")
    if not raw_type:
        logger.warning(
            "Resume payload missing decision type (keys=%s); treating as reject",
            list(payload.keys()),
        )
        return ParsedLcDecision(decision_type="reject")

    decision_type = str(raw_type).lower()
    edited_args = _extract_edited_args(payload) if decision_type == "edit" else None
    message = _extract_message(payload)
    return ParsedLcDecision(
        decision_type=decision_type,
        edited_args=edited_args,
        message=message,
    )


def _extract_edited_args(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Pull non-empty edited args from either the LC nested or flat shape."""
    edited_action = payload.get("edited_action")
    if isinstance(edited_action, dict):
        nested = edited_action.get("args")
        if isinstance(nested, dict) and nested:
            return nested
    flat = payload.get("args")
    if isinstance(flat, dict) and flat:
        return flat
    return None


def _extract_message(payload: dict[str, Any]) -> str | None:
    """Pull a non-empty user-feedback string, accepting either field name."""
    raw = payload.get("feedback") or payload.get("message")
    if isinstance(raw, str) and raw.strip():
        return raw
    return None


__all__ = ["ParsedLcDecision", "parse_lc_envelope"]
