"""Compose the ``<tools>`` block from per-tool vertical-slice folders.

Each tool lives in ``prompts/tools/<name>/`` with ``description.md`` and an
``example.md``. Visibility variants live in ``{private,team}/`` subfolders.
"""

from __future__ import annotations

from app.db import ChatVisibility

from ...tools import MAIN_AGENT_SURFSENSE_TOOL_NAMES_ORDERED
from .load_md import read_prompt_md

_MEMORY_VARIANT_TOOLS: frozenset[str] = frozenset({"update_memory"})


def _tool_fragment(tool_name: str, variant: str, leaf: str) -> str:
    if tool_name in _MEMORY_VARIANT_TOOLS:
        return read_prompt_md(f"tools/{tool_name}/{variant}/{leaf}")
    return read_prompt_md(f"tools/{tool_name}/{leaf}")


def _format_tool_label(tool_name: str) -> str:
    return tool_name.replace("_", " ").title()


def build_tools_instruction_block(
    *,
    visibility: ChatVisibility,
    enabled_tool_names: set[str] | None,
    disabled_tool_names: set[str] | None,
) -> str:
    """Render ``<tools>``. ``task`` is always included: at least ``deliverables``
    and ``knowledge_base`` are always in ``<specialists>`` (see constants)."""
    variant = "team" if visibility == ChatVisibility.SEARCH_SPACE else "private"

    parts: list[str] = ["\n<tools>\n"]

    for tool_name in MAIN_AGENT_SURFSENSE_TOOL_NAMES_ORDERED:
        if enabled_tool_names is not None and tool_name not in enabled_tool_names:
            continue

        description = _tool_fragment(tool_name, variant, "description.md")
        example = _tool_fragment(tool_name, variant, "example.md")

        if not description and not example:
            continue

        if description:
            parts.append(description + "\n")
        if example:
            parts.append("\n" + example + "\n")
        parts.append("\n")

    task_description = read_prompt_md("tools/task/description.md")
    task_example = read_prompt_md("tools/task/example.md")
    if task_description:
        parts.append(task_description + "\n")
    if task_example:
        parts.append("\n" + task_example + "\n")
    parts.append("\n")

    known_disabled = (
        set(disabled_tool_names) & set(MAIN_AGENT_SURFSENSE_TOOL_NAMES_ORDERED)
        if disabled_tool_names
        else set()
    )
    if known_disabled:
        disabled_list = ", ".join(
            _format_tool_label(n)
            for n in MAIN_AGENT_SURFSENSE_TOOL_NAMES_ORDERED
            if n in known_disabled
        )
        parts.append(
            "<disabled_tools>\n"
            f"Disabled for this session: {disabled_list}.\n"
            "Don't claim you can use them. If the user needs that capability,\n"
            "delegate with `task` when a specialist covers it; otherwise say\n"
            "the tool is disabled.\n"
            "</disabled_tools>\n"
        )

    parts.append("</tools>\n")
    return "".join(parts)
