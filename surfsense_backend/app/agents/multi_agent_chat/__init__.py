"""
Multi-agent chat (LangChain Subagents pattern).

**Layout (SRP)**

- :mod:`expert_agent.builtins` — general categories from the tool registry (research, memory, deliverables — not tied to one vendor).
- :mod:`expert_agent.connectors` — external integrations (one subgraph per product where split).
- :mod:`core` — prompts, compiled subgraph helper, delegation, registry subsets, tool-factory kwargs (:mod:`core.bindings`).
- :mod:`routing` — supervisor-facing ``@tool`` routers → domain invoke.
- :mod:`supervisor` — orchestrator graph + ``supervisor_prompt.md``.
- :mod:`integration` — async ``create_multi_agent_chat`` composer (partitions MCP tools into experts).

Documentation:
https://docs.langchain.com/oss/python/langchain/multi-agent
https://docs.langchain.com/oss/python/langchain/multi-agent/subagents

Display name: ``multi-agent-chat`` — Python package: ``multi_agent_chat``.
"""

from app.agents.multi_agent_chat.expert_agent.builtins.deliverables import (
    build_deliverables_tools,
    build_deliverables_domain_agent,
)
from app.agents.multi_agent_chat.expert_agent.builtins.memory import (
    build_memory_tools,
    build_memory_domain_agent,
)
from app.agents.multi_agent_chat.expert_agent.builtins.research import (
    build_research_tools,
    build_research_domain_agent,
)
from app.agents.multi_agent_chat.expert_agent.connectors.calendar import (
    build_calendar_domain_agent,
    build_calendar_tools,
)
from app.agents.multi_agent_chat.expert_agent.connectors.confluence import (
    build_confluence_tools,
    build_confluence_domain_agent,
)
from app.agents.multi_agent_chat.expert_agent.connectors.discord import (
    build_discord_tools,
    build_discord_domain_agent,
)
from app.agents.multi_agent_chat.expert_agent.connectors.dropbox import (
    build_dropbox_tools,
    build_dropbox_domain_agent,
)
from app.agents.multi_agent_chat.expert_agent.connectors.gmail import (
    build_gmail_tools,
    build_gmail_domain_agent,
)
from app.agents.multi_agent_chat.expert_agent.connectors.google_drive import (
    build_google_drive_tools,
    build_google_drive_domain_agent,
)
from app.agents.multi_agent_chat.expert_agent.connectors.luma import (
    build_luma_tools,
    build_luma_domain_agent,
)
from app.agents.multi_agent_chat.expert_agent.connectors.notion import (
    build_notion_tools,
    build_notion_domain_agent,
)
from app.agents.multi_agent_chat.expert_agent.connectors.onedrive import (
    build_onedrive_tools,
    build_onedrive_domain_agent,
)
from app.agents.multi_agent_chat.expert_agent.connectors.teams import (
    build_teams_tools,
    build_teams_domain_agent,
)
from app.agents.multi_agent_chat.core import (
    REGISTRY_ROUTING_CATEGORY_KEYS,
    TOOL_NAMES_BY_CATEGORY,
    build_domain_agent,
    build_registry_dependencies,
    build_registry_tools_for_category,
    compose_child_task,
    connector_binding,
    extract_last_assistant_text,
    read_prompt_md,
)
from app.agents.multi_agent_chat.integration import create_multi_agent_chat
from app.agents.multi_agent_chat.routing import (
    DomainRoutingSpec,
    build_supervisor_routing_tools,
    routing_tools_from_specs,
)
from app.agents.multi_agent_chat.supervisor import build_supervisor_agent

__all__ = [
    "REGISTRY_ROUTING_CATEGORY_KEYS",
    "TOOL_NAMES_BY_CATEGORY",
    "DomainRoutingSpec",
    "build_calendar_domain_agent",
    "build_confluence_tools",
    "build_confluence_domain_agent",
    "build_deliverables_tools",
    "build_deliverables_domain_agent",
    "build_discord_tools",
    "build_discord_domain_agent",
    "build_domain_agent",
    "build_dropbox_tools",
    "build_dropbox_domain_agent",
    "build_gmail_tools",
    "build_gmail_domain_agent",
    "build_calendar_tools",
    "build_google_drive_tools",
    "build_google_drive_domain_agent",
    "build_luma_tools",
    "build_luma_domain_agent",
    "build_memory_tools",
    "build_memory_domain_agent",
    "build_notion_tools",
    "build_notion_domain_agent",
    "build_onedrive_tools",
    "build_onedrive_domain_agent",
    "build_registry_dependencies",
    "build_registry_tools_for_category",
    "build_research_tools",
    "build_research_domain_agent",
    "build_supervisor_agent",
    "build_supervisor_routing_tools",
    "build_teams_tools",
    "build_teams_domain_agent",
    "connector_binding",
    "compose_child_task",
    "create_multi_agent_chat",
    "extract_last_assistant_text",
    "read_prompt_md",
    "routing_tools_from_specs",
]
