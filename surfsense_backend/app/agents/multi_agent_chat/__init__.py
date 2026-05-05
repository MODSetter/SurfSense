"""Deepagents-backed routes: ``subagents/``; main-agent graph under ``main_agent/`` (SRP subpackages)."""

from __future__ import annotations

from .main_agent import create_surfsense_deep_agent

__all__ = ["create_surfsense_deep_agent"]
