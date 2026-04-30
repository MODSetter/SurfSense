"""Declarative description of one supervisor routing tool → domain agent."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DomainRoutingSpec:
    """One supervisor-facing routing ``@tool`` bound to a compiled domain graph.

    ``curated_context`` is optional for **any** route: when set, the routing tool prepends its return
    value into the child task via :func:`~app.agents.multi_agent_chat.core.delegation.compose_child_task`.
    :func:`build_supervisor_routing_tools` does not pass it (all routes treated the same); use when building specs manually.
    """

    tool_name: str
    description: str
    domain_agent: Any
    curated_context: Callable[[str], str | None] | None = None
