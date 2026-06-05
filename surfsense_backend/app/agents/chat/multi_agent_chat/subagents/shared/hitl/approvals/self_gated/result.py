"""Outcome contract returned by :func:`request_approval`.

Lives in its own file so callers that only need the type for annotations don't
drag in ``langgraph`` imports through the entry-point module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class HITLResult:
    """Outcome of a self-gated human-in-the-loop approval request.

    Attributes:
        rejected: ``True`` when the tool MUST NOT execute (user said no, or
            the wire envelope was unparseable). Always check this first.
        decision_type: Reason tag for logging / metrics —
            ``"approve" | "edit" | "reject" | "trusted" | "auto_approved"
            | "error"``. Callers shouldn't branch on this for control flow;
            use ``rejected`` for that.
        params: Final parameters to pass to the underlying tool. On
            ``"edit"`` this is the original ``params`` shallow-merged with
            the user's edits; otherwise it's a copy of the originals.
    """

    rejected: bool
    decision_type: str
    params: dict[str, Any] = field(default_factory=dict)


__all__ = ["HITLResult"]
