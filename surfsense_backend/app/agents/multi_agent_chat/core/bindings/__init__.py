"""Search-space / DB kwargs shared by ``new_chat`` tool factories (distinct from ``expert_agent.connectors`` integrations)."""

from app.agents.multi_agent_chat.core.bindings.binding import connector_binding

__all__ = ["connector_binding"]
