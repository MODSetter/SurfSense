"""Permissions vertical slice: rule model + allow/deny/ask enforcement.

Self-contained subsystem combining the permission rule engine (:mod:`.model`)
with the pattern-based allow/deny/ask middleware and its HITL fallback
(:mod:`.middleware`, :mod:`.ask`, :mod:`.deny`).

Public surface:
- rule model: ``Rule``, ``Ruleset``, ``RuleAction`` and the ``evaluate`` /
  ``evaluate_many`` / ``aggregate_action`` / ``wildcard_match`` helpers.
- middleware: ``build_permission_mw`` — the construction recipe shared by
  every agent stack.
"""

# isort: off
# Import order matters: the rule model must be bound on this package before the
# middleware loads, because the middleware transitively imports consumers (e.g.
# app.services.user_tool_allowlist) that re-import ``Rule``/``Ruleset`` from this
# package root. Loading ``.model`` first avoids a partially-initialized cycle.
from .model import (
    Rule,
    RuleAction,
    Ruleset,
    aggregate_action,
    evaluate,
    evaluate_many,
    wildcard_match,
)
from .middleware.factory import build_permission_mw

# isort: on

__all__ = [
    "Rule",
    "RuleAction",
    "Ruleset",
    "aggregate_action",
    "build_permission_mw",
    "evaluate",
    "evaluate_many",
    "wildcard_match",
]
