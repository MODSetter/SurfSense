"""Full-stack wiring (DB-scoped) on top of :mod:`routing` and :mod:`supervisor`."""

from app.agents.multi_agent_chat.integration.create_multi_agent_chat import create_multi_agent_chat

__all__ = ["create_multi_agent_chat"]
