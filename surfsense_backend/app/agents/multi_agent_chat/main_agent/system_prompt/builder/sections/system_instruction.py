"""Default ``<system_instruction>`` block for the main agent only."""

from __future__ import annotations

from app.db import ChatVisibility

from ..load_md import read_prompt_md

_PRIVATE_ORDER = (
    "agent_private.md",
    "kb_only_policy_private.md",
    "main_agent_tool_routing.md",
    "parameter_resolution.md",
    "memory_protocol_private.md",
)
_TEAM_ORDER = (
    "agent_team.md",
    "kb_only_policy_team.md",
    "main_agent_tool_routing.md",
    "parameter_resolution.md",
    "memory_protocol_team.md",
)


def build_default_system_instruction_xml(
    *,
    visibility: ChatVisibility,
    resolved_today: str,
) -> str:
    order = _TEAM_ORDER if visibility == ChatVisibility.SEARCH_SPACE else _PRIVATE_ORDER
    parts = [read_prompt_md(name) for name in order]
    body = "\n\n".join(p for p in parts if p)
    return f"\n<system_instruction>\n{body}\n\n</system_instruction>\n".format(
        resolved_today=resolved_today,
    )
