"""Specialized user-facing subagents for the SurfSense agent.

Each subagent is a :class:`deepagents.SubAgent` typed-dict spec passed to
:class:`deepagents.SubAgentMiddleware`, which materializes them as ephemeral
runnables invoked via the ``task`` tool.

Per-subagent permission rules are injected as a
:class:`PermissionMiddleware` entry inside the subagent's ``middleware``
field, mirroring opencode ``tool/task.ts`` which seeds child sessions with
deny rules for tools the parent does not want them touching (e.g.
``task``/``todowrite`` recursion, write tools for read-only research roles).
"""

from .config import (
    build_connector_negotiator_subagent,
    build_explore_subagent,
    build_report_writer_subagent,
    build_specialized_subagents,
)

__all__ = [
    "build_connector_negotiator_subagent",
    "build_explore_subagent",
    "build_report_writer_subagent",
    "build_specialized_subagents",
]
