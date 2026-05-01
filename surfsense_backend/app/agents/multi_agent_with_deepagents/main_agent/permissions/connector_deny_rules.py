"""Synthesized PermissionMiddleware deny rules for tools gated by connector."""

from __future__ import annotations

from .connector_gated_tool_names import iter_connector_gated_tools
from .rule import Rule


def synthesize_connector_deny_rules(
    *,
    available_connectors: list[str] | None,
    enabled_tool_names: set[str],
) -> list[Rule]:
    available = set(available_connectors or [])
    deny: list[Rule] = []
    for name, required in iter_connector_gated_tools():
        if name not in enabled_tool_names:
            continue
        if required not in available:
            deny.append(Rule(permission=name, pattern="*", action="deny"))
    return deny
