"""``<tools>`` + ``<tool_call_examples>`` from ``system_prompt/markdown/{tools,examples}/``.

Only documents tools the main agent actually binds — not full ``new_chat``.
"""

from __future__ import annotations

from app.db import ChatVisibility

from ...tools import MAIN_AGENT_SURFSENSE_TOOL_NAMES_ORDERED
from .load_md import read_prompt_md

_MEMORY_VARIANT_TOOLS: frozenset[str] = frozenset({"update_memory"})


def _tool_fragment_path(tool_name: str, variant: str) -> str:
    if tool_name in _MEMORY_VARIANT_TOOLS:
        return f"tools/{tool_name}_{variant}.md"
    return f"tools/{tool_name}.md"


def _example_fragment_path(tool_name: str, variant: str) -> str:
    if tool_name in _MEMORY_VARIANT_TOOLS:
        return f"examples/{tool_name}_{variant}.md"
    return f"examples/{tool_name}.md"


def _format_tool_label(tool_name: str) -> str:
    return tool_name.replace("_", " ").title()


def build_tools_instruction_block(
    *,
    visibility: ChatVisibility,
    enabled_tool_names: set[str] | None,
    disabled_tool_names: set[str] | None,
) -> str:
    variant = "team" if visibility == ChatVisibility.SEARCH_SPACE else "private"

    parts: list[str] = []
    preamble = read_prompt_md("tools/_preamble.md")
    if preamble:
        parts.append(preamble + "\n")

    examples: list[str] = []

    for tool_name in MAIN_AGENT_SURFSENSE_TOOL_NAMES_ORDERED:
        if enabled_tool_names is not None and tool_name not in enabled_tool_names:
            continue

        instruction = read_prompt_md(_tool_fragment_path(tool_name, variant))
        if instruction:
            parts.append(instruction + "\n")

        example = read_prompt_md(_example_fragment_path(tool_name, variant))
        if example:
            examples.append(example + "\n")

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
            "\n"
            "DISABLED TOOLS (by user, main-agent scope):\n"
            f"These SurfSense tools were disabled on the main agent for this session: {disabled_list}.\n"
            "You do NOT have access to them and MUST NOT claim you can use them.\n"
            "If the user still needs that capability, delegate with **task** if a subagent covers it,\n"
            "otherwise explain it is disabled on the main agent for this session.\n"
        )

    parts.append("\n</tools>\n")

    if examples:
        parts.append("<tool_call_examples>")
        parts.extend(examples)
        parts.append("</tool_call_examples>\n")

    return "".join(parts)
