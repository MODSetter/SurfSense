"""Assemble the **main-agent** deep-agent system string only.

Sections (order matters): core instructions → provider → citations → dynamic
``<registry_subagents>`` → SurfSense ``<tools>``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.db import ChatVisibility

from .sections.citations import build_citations_section
from .sections.provider import build_provider_section
from .sections.registry_subagents import build_registry_subagents_section
from .sections.system_instruction import build_default_system_instruction_xml
from .sections.tools import build_tools_section


def build_main_agent_system_prompt(
    *,
    today: datetime | None = None,
    thread_visibility: ChatVisibility | None = None,
    enabled_tool_names: set[str] | None = None,
    disabled_tool_names: set[str] | None = None,
    custom_system_instructions: str | None = None,
    use_default_system_instructions: bool = True,
    citations_enabled: bool = True,
    model_name: str | None = None,
    registry_subagent_prompt_lines: list[tuple[str, str]] | None = None,
) -> str:
    resolved_today = (today or datetime.now(UTC)).astimezone(UTC).date().isoformat()
    visibility = thread_visibility or ChatVisibility.PRIVATE

    if custom_system_instructions and custom_system_instructions.strip():
        system_block = custom_system_instructions.format(resolved_today=resolved_today)
    elif use_default_system_instructions:
        system_block = build_default_system_instruction_xml(
            visibility=visibility,
            resolved_today=resolved_today,
        )
    else:
        system_block = ""

    system_block += build_provider_section(model_name=model_name)
    system_block += build_citations_section(citations_enabled=citations_enabled)
    system_block += build_registry_subagents_section(registry_subagent_prompt_lines)
    system_block += build_tools_section(
        visibility=visibility,
        enabled_tool_names=enabled_tool_names,
        disabled_tool_names=disabled_tool_names,
    )
    return system_block
