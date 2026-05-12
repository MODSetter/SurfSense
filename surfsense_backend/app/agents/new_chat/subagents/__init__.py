"""Specialized user-facing subagents for the SurfSense agent.

The :class:`deepagents.SubAgentMiddleware` already provides the
materialization machinery (each :class:`deepagents.SubAgent` typed-dict
spec is compiled into an ephemeral runnable invoked via the ``task``
tool); what's specific to SurfSense is the *seeding* of those subagents
with declarative deny rules.

Per-subagent permission rules are injected as a
:class:`PermissionMiddleware` entry inside the subagent's ``middleware``
field. The auto-deny pattern (e.g. forbid ``task``/``todowrite``
recursion, block write tools for read-only research roles) is borrowed
from OpenCode's ``packages/opencode/src/tool/task.ts``, which has
analogous logic for restricting child sessions.
"""

from .config import (
    build_connector_negotiator_subagent,
    build_explore_subagent,
    build_report_writer_subagent,
    build_specialized_subagents,
)
from .providers.linear import build_linear_specialist_subagent
from .providers.slack import build_slack_specialist_subagent

__all__ = [
    "build_connector_negotiator_subagent",
    "build_explore_subagent",
    "build_linear_specialist_subagent",
    "build_report_writer_subagent",
    "build_slack_specialist_subagent",
    "build_specialized_subagents",
]
