"""SurfSense supervisor middleware (parity with the main single-agent chat, minus subagents)."""

from app.agents.multi_agent_chat.middleware.supervisor_stack import (
    build_supervisor_middleware_stack,
    parse_thread_id_for_action_log,
)

__all__ = [
    "build_supervisor_middleware_stack",
    "parse_thread_id_for_action_log",
]
