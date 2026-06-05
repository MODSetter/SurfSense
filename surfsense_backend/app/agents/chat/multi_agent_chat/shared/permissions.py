"""
Wildcard pattern matching + rule evaluation for the SurfSense permission system.

Ported from OpenCode's ``packages/opencode/src/permission/evaluate.ts`` and
``packages/opencode/src/util/wildcard.ts``. LangChain has no rule-based
permission evaluator, so we keep OpenCode's semantics intact:

- ``Wildcard.match`` matches both the ``permission`` and the ``pattern``
  fields of a rule against the requested ``(permission, pattern)`` pair.
  ``*`` matches any segment, ``**`` matches across separators.
- The evaluator runs ``findLast`` over the **flattened** list of rules
  from all rulesets — last matching rule wins.
- The default fallback is ``ask`` (NOT deny), matching OpenCode.
- Multi-pattern requests AND together: if ANY pattern resolves to
  ``deny``, the whole request is denied; if ANY needs ``ask``, an
  interrupt is raised; only when all patterns ``allow`` does the
  request proceed.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal

RuleAction = Literal["allow", "deny", "ask"]


@dataclass(frozen=True)
class Rule:
    """A single permission rule.

    Attributes:
        permission: A wildcard-matched permission identifier
            (e.g. ``"edit"``, ``"linear_*"``, ``"mcp:*"``,
            ``"doom_loop"``). Anchored at start AND end of the input.
        pattern: A wildcard-matched pattern over the request payload
            (e.g. ``"/documents/secrets/**"``, ``"page_id=123"``,
            ``"*"``). Anchored at start AND end.
        action: One of ``"allow"`` / ``"deny"`` / ``"ask"``.
    """

    permission: str
    pattern: str
    action: RuleAction


@dataclass
class Ruleset:
    """A list of rules with an associated origin used for debugging."""

    rules: list[Rule] = field(default_factory=list)
    origin: str = "unknown"  # e.g. "defaults", "global", "space", "thread", "runtime"


# -----------------------------------------------------------------------------
# Wildcard matcher
# -----------------------------------------------------------------------------


_GLOB_TOKEN = re.compile(r"\*\*|\*|[^*]+")


def _wildcard_to_regex(pattern: str) -> re.Pattern[str]:
    """Translate an opencode-style wildcard pattern to a compiled regex.

    Rules:
    - ``**`` matches any sequence of any characters (including separators).
    - ``*`` matches any sequence of characters that does **not** include
      the path separator ``/`` — same as glob.
    - All other characters match literally.
    - The pattern is anchored at both ends (``^...$``).
    """
    parts: list[str] = ["^"]
    for token in _GLOB_TOKEN.findall(pattern):
        if token == "**":
            parts.append(r".*")
        elif token == "*":
            parts.append(r"[^/]*")
        else:
            parts.append(re.escape(token))
    parts.append("$")
    return re.compile("".join(parts))


_REGEX_CACHE: dict[str, re.Pattern[str]] = {}


def wildcard_match(value: str, pattern: str) -> bool:
    """Return True if ``value`` matches the wildcard ``pattern``.

    Special case: a bare ``"*"`` pattern matches any value, including
    those containing ``/`` separators. This mirrors opencode's
    ``Wildcard.match`` short-circuit and matches the convention that
    ``pattern="*"`` means "any pattern" in permission rules.
    """
    if pattern == "*":
        return True
    compiled = _REGEX_CACHE.get(pattern)
    if compiled is None:
        compiled = _wildcard_to_regex(pattern)
        _REGEX_CACHE[pattern] = compiled
    return compiled.match(value) is not None


# -----------------------------------------------------------------------------
# Evaluator
# -----------------------------------------------------------------------------


def evaluate(
    permission: str,
    pattern: str,
    *rulesets: Ruleset | Iterable[Rule],
) -> Rule:
    """Find the last rule matching ``(permission, pattern)`` from ``rulesets``.

    Mirrors opencode ``permission/evaluate.ts:9-15`` precisely:
    - Flatten rulesets in argument order.
    - Walk the flat list **in reverse**.
    - First reverse-match wins (i.e. the last specified rule wins).
    - When no rule matches, default to ``Rule(permission, "*", "ask")``.

    Args:
        permission: The permission identifier being requested
            (e.g. tool name, ``"edit"``, ``"doom_loop"``).
        pattern: The request-specific pattern (e.g. file path,
            primary arg value). Use ``"*"`` when no specific pattern
            applies.
        *rulesets: Layered rulesets, applied earliest to latest. Later
            rulesets override earlier ones.

    Returns:
        The matched :class:`Rule`, or the default ask fallback.
    """
    flat: list[Rule] = []
    for rs in rulesets:
        if isinstance(rs, Ruleset):
            flat.extend(rs.rules)
        else:
            flat.extend(rs)

    for rule in reversed(flat):
        if wildcard_match(permission, rule.permission) and wildcard_match(
            pattern, rule.pattern
        ):
            return rule

    return Rule(permission=permission, pattern="*", action="ask")


def evaluate_many(
    permission: str,
    patterns: Iterable[str],
    *rulesets: Ruleset | Iterable[Rule],
) -> list[Rule]:
    """Evaluate ``permission`` against each of ``patterns`` (multi-pattern AND).

    Returns the list of resolved rules in the same order as ``patterns``.
    The caller is responsible for combining the results — opencode-style
    multi-pattern AND collapses ``deny`` first, then ``ask``, then
    ``allow``.
    """
    return [evaluate(permission, p, *rulesets) for p in patterns]


def aggregate_action(rules: Iterable[Rule]) -> RuleAction:
    """Collapse a list of per-pattern rules into one action.

    Order:
    1. If any rule is ``deny`` -> ``deny``.
    2. Else if any rule is ``ask`` -> ``ask``.
    3. Else if at least one rule is ``allow`` -> ``allow``.
    4. Else (empty input) -> ``ask`` (safe default mirroring ``evaluate``).

    Mirrors opencode's behavior in ``permission/index.ts:180-272``.
    """
    saw_ask = False
    saw_allow = False
    for rule in rules:
        if rule.action == "deny":
            return "deny"
        if rule.action == "ask":
            saw_ask = True
        elif rule.action == "allow":
            saw_allow = True
    if saw_ask:
        return "ask"
    if saw_allow:
        return "allow"
    return "ask"


__all__ = [
    "Rule",
    "RuleAction",
    "Ruleset",
    "aggregate_action",
    "evaluate",
    "evaluate_many",
    "wildcard_match",
]
