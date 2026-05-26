"""Per-action config schemas: one file per action type registered in v1."""

from __future__ import annotations

from .agent_task import AgentTaskActionConfig

__all__ = [
    "AgentTaskActionConfig",
]
