"""Resolve patterns for a tool call and aggregate the resulting rules.

Two stages run on every tool call:

1. :func:`resolve_patterns` asks the tool's resolver (or the default) for
   the wildcard patterns the rule engine should evaluate. Resolver
   failures fall back to the bare tool name so a buggy resolver can't
   cascade into permission decisions.
2. :func:`evaluate_tool_call` runs the rule engine against those patterns
   and collapses the per-pattern rules into a single action
   (``deny`` > ``ask`` > ``allow``).
"""

from __future__ import annotations

import logging
from typing import Any

from app.agents.multi_agent_chat.shared.permissions import (
    Rule,
    RuleAction,
    Ruleset,
    aggregate_action,
    evaluate_many,
)

from .pattern_resolver import PatternResolver, default_pattern_resolver

logger = logging.getLogger(__name__)


def resolve_patterns(
    tool_name: str,
    args: dict[str, Any],
    pattern_resolvers: dict[str, PatternResolver],
) -> list[str]:
    resolver = pattern_resolvers.get(tool_name, default_pattern_resolver(tool_name))
    try:
        patterns = resolver(args or {})
    except Exception:
        logger.exception("Pattern resolver for %s raised; using bare name", tool_name)
        patterns = [tool_name]
    if not patterns:
        patterns = [tool_name]
    return patterns


def evaluate_tool_call(
    tool_name: str,
    args: dict[str, Any],
    pattern_resolvers: dict[str, PatternResolver],
    rulesets: list[Ruleset],
) -> tuple[RuleAction, list[str], list[Rule]]:
    patterns = resolve_patterns(tool_name, args, pattern_resolvers)
    rules = evaluate_many(tool_name, patterns, *rulesets)
    action = aggregate_action(rules)
    return action, patterns, rules


__all__ = ["evaluate_tool_call", "resolve_patterns"]
