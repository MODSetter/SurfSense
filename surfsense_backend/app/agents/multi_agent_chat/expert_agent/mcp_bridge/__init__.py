"""Prompt-backed subgraphs for MCP OAuth integrations without a native tool registry slice."""

from app.agents.multi_agent_chat.expert_agent.mcp_bridge.agent import build_mcp_route_domain_agent

__all__ = ["build_mcp_route_domain_agent"]
