"""Schema-level description for the ``task`` tool.

Loaded from ``prompts/tools/task/description.md`` so the tool-schema text
and the ``<tools>`` block render from the same source.
"""

from __future__ import annotations

from app.agents.chat.multi_agent_chat.main_agent.system_prompt.builder.load_md import (
    read_prompt_md,
)

TASK_TOOL_DESCRIPTION: str = read_prompt_md("tools/task/description.md")

__all__ = ["TASK_TOOL_DESCRIPTION"]
