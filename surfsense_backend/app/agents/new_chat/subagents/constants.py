"""Shared constants for provider subagent safety policies."""

from __future__ import annotations

# Generic mutation-deny patterns for read-only specialist roles.
WRITE_TOOL_DENY_PATTERNS: tuple[str, ...] = (
    "*create*",
    "*update*",
    "*delete*",
    "*send*",
    "*write*",
    "*edit*",
    "*move*",
    "*mkdir*",
    "*upload*",
    "edit_file",
    "write_file",
    "move_file",
    "mkdir",
    "update_memory",
    "update_memory_team",
    "update_memory_private",
)

# Tools that mutate virtual KB filesystem or parent/global chat state.
# Provider specialists should not mutate these surfaces directly.
NON_PROVIDER_STATE_MUTATION_DENY: frozenset[str] = frozenset(
    {
        # Exact tool names from shared deny patterns.
        *{
            name
            for name in WRITE_TOOL_DENY_PATTERNS
            if "*" not in name
        },
        # Additional non-provider state mutation controls.
        "write_todos",
        "task",
    }
)

