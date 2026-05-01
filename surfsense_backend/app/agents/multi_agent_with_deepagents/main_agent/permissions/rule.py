"""Minimal permission rule type (mirrors OpenCode semantics used by PermissionMiddleware)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RuleAction = Literal["allow", "deny", "ask"]


@dataclass(frozen=True)
class Rule:
    permission: str
    pattern: str
    action: RuleAction
