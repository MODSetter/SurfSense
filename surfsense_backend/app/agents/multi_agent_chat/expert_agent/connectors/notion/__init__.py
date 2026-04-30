"""Notion connector slice."""

from app.agents.multi_agent_chat.expert_agent.connectors.notion.agent import build_notion_domain_agent
from app.agents.multi_agent_chat.expert_agent.connectors.notion.slice_tools import (
    build_notion_tools,
)

__all__ = [
    "build_notion_tools",
    "build_notion_domain_agent",
]
