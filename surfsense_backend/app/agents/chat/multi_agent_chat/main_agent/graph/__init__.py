"""Sync compile of the main-agent LangGraph graph (middleware + ``create_agent``)."""

from __future__ import annotations

from .compile_graph_sync import build_compiled_agent_graph_sync

__all__ = ["build_compiled_agent_graph_sync"]
