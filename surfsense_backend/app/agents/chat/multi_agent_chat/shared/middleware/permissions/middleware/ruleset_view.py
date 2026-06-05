"""Combined view over static + runtime rulesets.

Static rulesets come from the agent factory (defaults, space-scoped,
thread-scoped, etc.). The runtime ruleset is the in-memory one that
:func:`runtime_promote.persist_always` extends when the user replies
``"approve_always"``. Evaluators always see them merged in this order so
newly-promoted rules apply to subsequent calls.
"""

from __future__ import annotations

from app.agents.chat.multi_agent_chat.shared.permissions import (
    Ruleset,
    aggregate_action,
    evaluate_many,
)


def all_rulesets(
    static_rulesets: list[Ruleset], runtime_ruleset: Ruleset
) -> list[Ruleset]:
    return [*static_rulesets, runtime_ruleset]


def globally_denied(tool_name: str, rulesets: list[Ruleset]) -> bool:
    """True if an unconditional deny rule blocks every invocation of ``tool_name``."""
    rules = evaluate_many(tool_name, ["*"], *rulesets)
    return aggregate_action(rules) == "deny"


__all__ = ["all_rulesets", "globally_denied"]
