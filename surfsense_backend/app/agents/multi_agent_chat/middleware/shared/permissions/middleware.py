"""Main-agent permission middleware (full ask/deny/allow rules)."""

from __future__ import annotations

from app.agents.new_chat.middleware import PermissionMiddleware
from app.agents.new_chat.permissions import Ruleset


def build_full_permission_mw(rulesets: list[Ruleset]) -> PermissionMiddleware | None:
    return PermissionMiddleware(rulesets=rulesets) if rulesets else None
