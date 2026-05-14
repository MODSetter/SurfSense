"""SurfSense's subagent contribution: deepagents spec + permission ruleset."""

from __future__ import annotations

from dataclasses import dataclass

from deepagents import SubAgent

from app.agents.new_chat.permissions import Ruleset


@dataclass(frozen=True, slots=True)
class SurfSenseSubagentSpec:
    """A subagent contribution from a SurfSense route.

    Attributes:
        spec: The deepagents-shaped dict handed to ``create_agent``. Holds
            only fields ``deepagents.SubAgent`` recognises.
        ruleset: Permission rules this subagent contributes. The orchestrator
            layers them into the subagent's :class:`PermissionMiddleware`,
            so each subagent owns its own ruleset without aliasing the
            shared rule engine.
    """

    spec: SubAgent
    ruleset: Ruleset


__all__ = ["SurfSenseSubagentSpec"]
