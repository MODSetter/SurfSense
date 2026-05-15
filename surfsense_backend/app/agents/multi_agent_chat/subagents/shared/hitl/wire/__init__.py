"""Single source of truth for the langchain HITL wire format used by every approval path.

Public surface:
- :func:`build_lc_hitl_payload` — outbound (interrupt argument).
- :func:`parse_lc_envelope` + :class:`ParsedLcDecision` — inbound (resume value).
- Decision-type constants for callers that care about identity rather than literals.
"""

from .decision import ParsedLcDecision, parse_lc_envelope
from .payload import (
    LC_DECISION_APPROVE,
    LC_DECISION_EDIT,
    LC_DECISION_REJECT,
    SURFSENSE_DECISION_APPROVE_ALWAYS,
    build_lc_hitl_payload,
)

__all__ = [
    "LC_DECISION_APPROVE",
    "LC_DECISION_EDIT",
    "LC_DECISION_REJECT",
    "SURFSENSE_DECISION_APPROVE_ALWAYS",
    "ParsedLcDecision",
    "build_lc_hitl_payload",
    "parse_lc_envelope",
]
