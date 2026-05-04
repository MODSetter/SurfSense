"""Registry-backed subagent builders and helpers."""

from __future__ import annotations

from .registry import (
    SUBAGENT_BUILDERS_BY_NAME,
    SubagentBuilder,
    build_subagents,
    get_subagents_to_exclude,
    main_prompt_registry_subagent_lines,
)

__all__ = [
    "SUBAGENT_BUILDERS_BY_NAME",
    "SubagentBuilder",
    "build_subagents",
    "get_subagents_to_exclude",
    "main_prompt_registry_subagent_lines",
]
