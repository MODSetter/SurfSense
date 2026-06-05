"""Promote an ``"approve_always"`` reply into in-memory allow rules.

Subsequent calls within the same agent instance match these new rules and
proceed without prompting. Durable persistence (to ``agent_permission_rules``)
is the streaming layer's job — this module keeps the in-memory copy only.
"""

from __future__ import annotations

from app.agents.multi_agent_chat.shared.permissions import Rule, Ruleset


def persist_always(
    runtime_ruleset: Ruleset, tool_name: str, patterns: list[str]
) -> None:
    for pattern in patterns:
        runtime_ruleset.rules.append(
            Rule(permission=tool_name, pattern=pattern, action="allow")
        )


__all__ = ["persist_always"]
