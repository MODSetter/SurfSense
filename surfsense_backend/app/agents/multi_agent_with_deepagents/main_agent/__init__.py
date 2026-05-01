"""Main-agent deep agent: ``runtime/`` (factory), ``graph/`` (compile), ``system_prompt/``, etc."""

from __future__ import annotations

from .runtime import create_surfsense_deep_agent

__all__ = ["create_surfsense_deep_agent"]
