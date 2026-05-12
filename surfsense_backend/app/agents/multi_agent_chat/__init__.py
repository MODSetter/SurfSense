"""Deepagents-backed routes: ``subagents/``; main-agent graph under ``main_agent/`` (SRP subpackages)."""

from __future__ import annotations

from .main_agent import create_multi_agent_chat_deep_agent

__all__ = ["create_multi_agent_chat_deep_agent"]
