"""Central registry of route ``build_subagent`` callables (keyed by ``NAME``)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from deepagents import SubAgent
from langchain_core.language_models import BaseChatModel

from app.agents.multi_agent_with_deepagents.subagents.builtins.deliverables.agent import (
    build_subagent as build_deliverables_subagent,
)
from app.agents.multi_agent_with_deepagents.subagents.builtins.memory.agent import (
    build_subagent as build_memory_subagent,
)
from app.agents.multi_agent_with_deepagents.subagents.builtins.research.agent import (
    build_subagent as build_research_subagent,
)
from app.agents.multi_agent_with_deepagents.subagents.connectors.airtable.agent import (
    build_subagent as build_airtable_subagent,
)
from app.agents.multi_agent_with_deepagents.subagents.connectors.calendar.agent import (
    build_subagent as build_calendar_subagent,
)
from app.agents.multi_agent_with_deepagents.subagents.connectors.clickup.agent import (
    build_subagent as build_clickup_subagent,
)
from app.agents.multi_agent_with_deepagents.subagents.connectors.confluence.agent import (
    build_subagent as build_confluence_subagent,
)
from app.agents.multi_agent_with_deepagents.subagents.connectors.discord.agent import (
    build_subagent as build_discord_subagent,
)
from app.agents.multi_agent_with_deepagents.subagents.connectors.dropbox.agent import (
    build_subagent as build_dropbox_subagent,
)
from app.agents.multi_agent_with_deepagents.subagents.connectors.gmail.agent import (
    build_subagent as build_gmail_subagent,
)
from app.agents.multi_agent_with_deepagents.subagents.connectors.google_drive.agent import (
    build_subagent as build_google_drive_subagent,
)
from app.agents.multi_agent_with_deepagents.subagents.connectors.jira.agent import (
    build_subagent as build_jira_subagent,
)
from app.agents.multi_agent_with_deepagents.subagents.connectors.linear.agent import (
    build_subagent as build_linear_subagent,
)
from app.agents.multi_agent_with_deepagents.subagents.connectors.luma.agent import (
    build_subagent as build_luma_subagent,
)
from app.agents.multi_agent_with_deepagents.subagents.connectors.notion.agent import (
    build_subagent as build_notion_subagent,
)
from app.agents.multi_agent_with_deepagents.subagents.connectors.onedrive.agent import (
    build_subagent as build_onedrive_subagent,
)
from app.agents.multi_agent_with_deepagents.subagents.connectors.slack.agent import (
    build_subagent as build_slack_subagent,
)
from app.agents.multi_agent_with_deepagents.subagents.connectors.teams.agent import (
    build_subagent as build_teams_subagent,
)
from app.agents.multi_agent_with_deepagents.subagents.shared.permissions import (
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

__all__ = [
    "SUBAGENT_BUILDERS_BY_NAME",
    "SubagentBuilder",
    "build_subagents",
]


def build_subagents(
    *,
    dependencies: dict[str, Any],
    model: BaseChatModel | None = None,
    extra_middleware: Sequence[Any] | None = None,
    mcp_tools_by_agent: dict[str, ToolsPermissions] | None = None,
    only_names: frozenset[str] | None = None,
) -> list[SubAgent]:
    """Build registry route specs.

    ``memory`` and ``research`` are never included (main agent holds those tools).
    When ``only_names`` is set, only matching routes among the remainder are built.
    """
    mcp = mcp_tools_by_agent or {}
    specs: list[SubAgent] = []
    for name in sorted(SUBAGENT_BUILDERS_BY_NAME):
        if name in ("memory", "research"):
            continue
        if only_names is not None and name not in only_names:
            continue
        builder = SUBAGENT_BUILDERS_BY_NAME[name]
        specs.append(
            builder(
                dependencies=dependencies,
                model=model,
                extra_middleware=extra_middleware,
                extra_tools_bucket=mcp.get(name),
            ),
        )
    return specs
