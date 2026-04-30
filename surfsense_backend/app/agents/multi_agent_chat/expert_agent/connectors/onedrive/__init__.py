"""Microsoft OneDrive connector slice."""

from app.agents.multi_agent_chat.expert_agent.connectors.onedrive.agent import build_onedrive_domain_agent
from app.agents.multi_agent_chat.expert_agent.connectors.onedrive.slice_tools import (
    build_onedrive_tools,
)

__all__ = [
    "build_onedrive_tools",
    "build_onedrive_domain_agent",
]
