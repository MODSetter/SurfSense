"""Derive shared permission context once; fan out to all three stack layers.

The context carries:
- ``rulesets``: full ask/deny/allow rules for the main-agent permission middleware.
- ``general_purpose_interrupt_on``: ``ask`` rules mirrored as deepagents
  ``interrupt_on`` so HITL still triggers from inside ``task`` runs (subagents
  bypass the main-agent permission middleware).
- ``subagent_deny_mw``: a deny-only ``PermissionMiddleware`` instance shared
  across the general-purpose and registry subagent stacks.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from langchain_core.tools import BaseTool

from app.agents.new_chat.feature_flags import AgentFeatureFlags
from app.agents.new_chat.filesystem_selection import FilesystemMode
from app.agents.new_chat.middleware import PermissionMiddleware
from app.agents.new_chat.permissions import Rule, Ruleset
from app.agents.new_chat.tools.registry import BUILTIN_TOOLS

from ..flags import enabled


@dataclass(frozen=True)
class PermissionContext:
    rulesets: list[Ruleset]
    general_purpose_interrupt_on: dict[str, bool]
    subagent_deny_mw: PermissionMiddleware | None


def build_permission_context(
    *,
    flags: AgentFeatureFlags,
    filesystem_mode: FilesystemMode,
    tools: Sequence[BaseTool],
    available_connectors: list[str] | None,
) -> PermissionContext:
    is_desktop_fs = filesystem_mode == FilesystemMode.DESKTOP_LOCAL_FOLDER
    permission_enabled = enabled(flags, "enable_permission")

    rulesets: list[Ruleset] = []
    if permission_enabled or is_desktop_fs:
        rulesets.append(
            Ruleset(
                rules=[Rule(permission="*", pattern="*", action="allow")],
                origin="surfsense_defaults",
            )
        )
        if is_desktop_fs:
            rulesets.append(
                Ruleset(
                    rules=[
                        Rule(permission="rm", pattern="*", action="ask"),
                        Rule(permission="rmdir", pattern="*", action="ask"),
                        Rule(permission="move_file", pattern="*", action="ask"),
                        Rule(permission="edit_file", pattern="*", action="ask"),
                        Rule(permission="write_file", pattern="*", action="ask"),
                    ],
                    origin="desktop_safety",
                )
            )

    tool_names_in_use = {t.name for t in tools}

    if permission_enabled:
        available_set = set(available_connectors or [])
        synthesized: list[Rule] = []
        for tool_def in BUILTIN_TOOLS:
            if tool_def.name not in tool_names_in_use:
                continue
            rc = tool_def.required_connector
            if rc and rc not in available_set:
                synthesized.append(
                    Rule(permission=tool_def.name, pattern="*", action="deny")
                )
        if synthesized:
            rulesets.append(Ruleset(rules=synthesized, origin="connector_synthesized"))

    general_purpose_interrupt_on: dict[str, bool] = {
        rule.permission: True
        for rs in rulesets
        for rule in rs.rules
        if rule.action == "ask" and rule.permission in tool_names_in_use
    }

    deny_rulesets = [
        Ruleset(
            rules=[r for r in rs.rules if r.action == "deny"],
            origin=rs.origin,
        )
        for rs in rulesets
    ]
    deny_rulesets = [rs for rs in deny_rulesets if rs.rules]

    subagent_deny_mw: PermissionMiddleware | None = (
        PermissionMiddleware(rulesets=deny_rulesets) if deny_rulesets else None
    )

    return PermissionContext(
        rulesets=rulesets,
        general_purpose_interrupt_on=general_purpose_interrupt_on,
        subagent_deny_mw=subagent_deny_mw,
    )
