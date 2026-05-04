"""Central registry of route ``build_subagent`` callables (keyed by ``NAME``)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from deepagents import SubAgent
from langchain_core.language_models import BaseChatModel

from app.agents.multi_agent_chat.constants import (
    SUBAGENT_TO_REQUIRED_CONNECTOR_MAP,
)
from app.agents.multi_agent_chat.subagents.builtins.deliverables.agent import (
    build_subagent as build_deliverables_subagent,
)
from app.agents.multi_agent_chat.subagents.builtins.memory.agent import (
    build_subagent as build_memory_subagent,
)
from app.agents.multi_agent_chat.subagents.builtins.research.agent import (
    build_subagent as build_research_subagent,
)
from app.agents.multi_agent_chat.subagents.connectors.airtable.agent import (
    build_subagent as build_airtable_subagent,
)
from app.agents.multi_agent_chat.subagents.connectors.calendar.agent import (
    build_subagent as build_calendar_subagent,
)
from app.agents.multi_agent_chat.subagents.connectors.clickup.agent import (
    build_subagent as build_clickup_subagent,
)
from app.agents.multi_agent_chat.subagents.connectors.confluence.agent import (
    build_subagent as build_confluence_subagent,
)
from app.agents.multi_agent_chat.subagents.connectors.discord.agent import (
    build_subagent as build_discord_subagent,
)
from app.agents.multi_agent_chat.subagents.connectors.dropbox.agent import (
    build_subagent as build_dropbox_subagent,
)
from app.agents.multi_agent_chat.subagents.connectors.gmail.agent import (
    build_subagent as build_gmail_subagent,
)
from app.agents.multi_agent_chat.subagents.connectors.google_drive.agent import (
    build_subagent as build_google_drive_subagent,
)
from app.agents.multi_agent_chat.subagents.connectors.jira.agent import (
    build_subagent as build_jira_subagent,
)
from app.agents.multi_agent_chat.subagents.connectors.linear.agent import (
    build_subagent as build_linear_subagent,
)
from app.agents.multi_agent_chat.subagents.connectors.luma.agent import (
    build_subagent as build_luma_subagent,
)
from app.agents.multi_agent_chat.subagents.connectors.notion.agent import (
    build_subagent as build_notion_subagent,
)
from app.agents.multi_agent_chat.subagents.connectors.onedrive.agent import (
    build_subagent as build_onedrive_subagent,
)
from app.agents.multi_agent_chat.subagents.connectors.slack.agent import (
    build_subagent as build_slack_subagent,
)
from app.agents.multi_agent_chat.subagents.connectors.teams.agent import (
    build_subagent as build_teams_subagent,
)
from app.agents.multi_agent_chat.subagents.shared.md_file_reader import (
    read_md_file,
)
from app.agents.multi_agent_chat.subagents.shared.permissions import (
    ToolsPermissions,
)


class SubagentBuilder(Protocol):
    def __call__(
        self,
        *,
        dependencies: dict[str, Any],
        model: BaseChatModel | None = None,
        extra_middleware: Sequence[Any] | None = None,
        extra_tools_bucket: ToolsPermissions | None = None,
    ) -> SubAgent: ...


SUBAGENT_BUILDERS_BY_NAME: dict[str, SubagentBuilder] = {
    "airtable": build_airtable_subagent,
    "calendar": build_calendar_subagent,
    "clickup": build_clickup_subagent,
    "confluence": build_confluence_subagent,
    "deliverables": build_deliverables_subagent,
    "discord": build_discord_subagent,
    "dropbox": build_dropbox_subagent,
    "gmail": build_gmail_subagent,
    "google_drive": build_google_drive_subagent,
    "jira": build_jira_subagent,
    "linear": build_linear_subagent,
    "luma": build_luma_subagent,
    "memory": build_memory_subagent,
    "notion": build_notion_subagent,
    "onedrive": build_onedrive_subagent,
    "research": build_research_subagent,
    "slack": build_slack_subagent,
    "teams": build_teams_subagent,
}


def _route_resource_package(builder: SubagentBuilder) -> str:
    mod = builder.__module__
    return mod[: -len(".agent")] if mod.endswith(".agent") else mod.rsplit(".", 1)[0]


def main_prompt_registry_subagent_lines(exclude: list[str]) -> list[tuple[str, str]]:
    """(name, description) for registry specialists included for **task** (same rules as ``build_subagents``)."""
    banned = frozenset(("memory", "research")) | frozenset(exclude)
    rows: list[tuple[str, str]] = []
    for name in sorted(SUBAGENT_BUILDERS_BY_NAME):
        if name in banned:
            continue
        builder = SUBAGENT_BUILDERS_BY_NAME[name]
        pkg = _route_resource_package(builder)
        blurb = read_md_file(pkg, "description").strip()
        if not blurb:
            blurb = name.replace("_", " ").title()
        rows.append((name, blurb))
    return rows


def get_subagents_to_exclude(
    available_connectors: list[str] | None,
) -> list[str]:
    if available_connectors is None:
        return []
    available_tokens = frozenset(available_connectors)
    excluded_names: set[str] = set()
    for builder_name in SUBAGENT_BUILDERS_BY_NAME:
        required_tokens = SUBAGENT_TO_REQUIRED_CONNECTOR_MAP.get(builder_name)
        if required_tokens is None:
            excluded_names.add(builder_name)
            continue
        if not required_tokens:
            continue
        if not (required_tokens & available_tokens):
            excluded_names.add(builder_name)
    return sorted(excluded_names)


def _filter_disabled_tools_in_place(
    spec: SubAgent,
    disabled_names: frozenset[str],
) -> None:
    """Drop UI-disabled tools from ``spec["tools"]`` and ``spec["interrupt_on"]``."""
    if not disabled_names:
        return
    tools = spec.get("tools")  # type: ignore[typeddict-item]
    if isinstance(tools, list):
        spec["tools"] = [  # type: ignore[typeddict-unknown-key]
            t for t in tools if getattr(t, "name", None) not in disabled_names
        ]
    interrupt_on = spec.get("interrupt_on")  # type: ignore[typeddict-item]
    if isinstance(interrupt_on, dict):
        spec["interrupt_on"] = {  # type: ignore[typeddict-unknown-key]
            k: v for k, v in interrupt_on.items() if k not in disabled_names
        }


def build_subagents(
    *,
    dependencies: dict[str, Any],
    model: BaseChatModel | None = None,
    extra_middleware: Sequence[Any] | None = None,
    mcp_tools_by_agent: dict[str, ToolsPermissions] | None = None,
    exclude: list[str] | None = None,
    disabled_tools: list[str] | None = None,
) -> list[SubAgent]:
    """Build registry subagents; skip memory/research; skip names in exclude."""
    mcp = mcp_tools_by_agent or {}
    specs: list[SubAgent] = []
    excluded = ["memory", "research"]
    if exclude:
        excluded.extend(exclude)
    disabled_names = frozenset(disabled_tools or ())
    for name in sorted(SUBAGENT_BUILDERS_BY_NAME):
        if name in excluded:
            continue
        builder = SUBAGENT_BUILDERS_BY_NAME[name]
        spec = builder(
            dependencies=dependencies,
            model=model,
            extra_middleware=extra_middleware,
            extra_tools_bucket=mcp.get(name),
        )
        _filter_disabled_tools_in_place(spec, disabled_names)
        specs.append(spec)
    return specs
