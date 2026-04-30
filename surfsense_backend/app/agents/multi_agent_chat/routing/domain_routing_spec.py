"""Declarative description of one supervisor routing tool → domain agent."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DomainRoutingSpec:
    """One ``@tool`` the supervisor calls to delegate to a compiled domain graph."""

    tool_name: str
    description: str
    domain_agent: Any
    curated_context: Callable[[str], str | None] | None = None
