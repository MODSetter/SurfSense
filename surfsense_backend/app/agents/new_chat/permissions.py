"""Backward-compatible shim.

The permission evaluator now lives in the shared agent kernel at
``app.agents.shared.permissions``. This module re-exports it so frozen
single-agent code (``chat_deepagent`` and ``subagents/*``) keeps working
until that stack is retired.
"""

from __future__ import annotations

from app.agents.shared.permissions import (
    Rule,
    RuleAction,
    Ruleset,
    aggregate_action,
    evaluate,
    evaluate_many,
    wildcard_match,
)

__all__ = [
    "Rule",
    "RuleAction",
    "Ruleset",
    "aggregate_action",
    "evaluate",
    "evaluate_many",
    "wildcard_match",
]
