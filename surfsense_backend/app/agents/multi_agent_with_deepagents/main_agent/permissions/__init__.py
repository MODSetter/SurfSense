"""Connector-gated tool deny rules and small permission helpers for the main-agent graph."""

from __future__ import annotations

from .connector_deny_rules import synthesize_connector_deny_rules
from .connector_gated_tool_names import iter_connector_gated_tools
from .rule import Rule

__all__ = [
    "Rule",
    "iter_connector_gated_tools",
    "synthesize_connector_deny_rules",
]
