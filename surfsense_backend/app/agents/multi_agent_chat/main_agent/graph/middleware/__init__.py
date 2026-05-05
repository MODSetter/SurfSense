"""Main-agent graph middleware assembly (SurfSense + LangChain + deepagents)."""

from __future__ import annotations

from .deepagent_stack import build_main_agent_deepagent_middleware

__all__ = ["build_main_agent_deepagent_middleware"]
