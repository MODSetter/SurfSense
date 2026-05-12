"""Main-agent ``<tools>`` block (memory + research builtins only; see ``main_agent.tools``)."""

from __future__ import annotations

from app.db import ChatVisibility

from ..tool_instruction_block import build_tools_instruction_block


def build_tools_section(
    *,
    visibility: ChatVisibility,
    enabled_tool_names: set[str] | None,
    disabled_tool_names: set[str] | None,
) -> str:
    return build_tools_instruction_block(
        visibility=visibility,
        enabled_tool_names=enabled_tool_names,
        disabled_tool_names=disabled_tool_names,
    )
