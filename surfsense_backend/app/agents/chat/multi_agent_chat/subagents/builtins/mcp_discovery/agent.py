"""``mcp_discovery`` route: ``SurfSenseSubagentSpec`` builder for deepagents.

Consolidates every MCP-backed connector plus interim native Gmail/Calendar
tools. The permission ruleset is derived from the runtime tool set (not a
static constant) because the MCP tool roster is per-user.
"""

from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from app.agents.chat.multi_agent_chat.shared.permissions import Rule, Ruleset
from app.agents.chat.multi_agent_chat.subagents.shared.md_file_reader import (
    read_md_file,
)
from app.agents.chat.multi_agent_chat.subagents.shared.spec import SurfSenseSubagentSpec
from app.agents.chat.multi_agent_chat.subagents.shared.subagent_builder import (
    pack_subagent,
)

from .tools.index import NAME, build_ruleset, load_tools


def _augment_allowlist_for_collision_prefixes(
    dependencies: dict[str, Any],
    tools: list[BaseTool],
) -> dict[str, Any]:
    """Keep "Always Allow" working for tools that got collision-prefixed.

    A tool trusted under its bare name (``search``) can later be renamed to
    ``notion_5_search`` once a second app also exposes ``search`` (Phase 2b
    collision resolution). The user's persisted allow-rule still keys on the
    bare name, so we add an alias allow-rule for the new exposed name when the
    original is already trusted. Returns ``dependencies`` unchanged when there
    is nothing to do.
    """
    by_subagent = dependencies.get("user_allowlist_by_subagent") or {}
    existing = by_subagent.get(NAME)
    if not isinstance(existing, Ruleset) or not existing.rules:
        return dependencies

    trusted_names = {r.permission for r in existing.rules if r.action == "allow"}
    alias_rules: list[Rule] = []
    for tool in tools:
        meta = getattr(tool, "metadata", None) or {}
        if not meta.get("mcp_collision_prefixed"):
            continue
        original = meta.get("mcp_original_tool_name")
        if original in trusted_names and tool.name not in trusted_names:
            alias_rules.append(
                Rule(permission=tool.name, pattern="*", action="allow")
            )

    if not alias_rules:
        return dependencies

    merged = Ruleset(
        origin=existing.origin,
        rules=[*existing.rules, *alias_rules],
    )
    return {
        **dependencies,
        "user_allowlist_by_subagent": {**by_subagent, NAME: merged},
    }


def build_subagent(
    *,
    dependencies: dict[str, Any],
    model: BaseChatModel | None = None,
    middleware_stack: dict[str, Any] | None = None,
    mcp_tools: list[BaseTool] | None = None,
) -> SurfSenseSubagentSpec:
    tools = load_tools(dependencies=dependencies, mcp_tools=mcp_tools)
    ruleset = build_ruleset(tools)
    dependencies = _augment_allowlist_for_collision_prefixes(dependencies, tools)
    description = (
        read_md_file(__package__, "description").strip()
        or "Acts on the user's connected apps (Slack, Jira, Notion, Gmail, ...) via MCP."
    )
    system_prompt = read_md_file(__package__, "system_prompt").strip()
    return pack_subagent(
        name=NAME,
        description=description,
        system_prompt=system_prompt,
        tools=tools,
        ruleset=ruleset,
        dependencies=dependencies,
        model=model,
        middleware_stack=middleware_stack,
    )
