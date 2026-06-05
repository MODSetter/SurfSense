"""Construction recipe for :class:`PermissionMiddleware` shared across stacks.

Single source of truth used by both the main-agent stack and every subagent
stack. Rule layers are evaluated earliest-to-latest (last match wins,
matching OpenCode's ``permission/index.ts`` evaluation order):

1. ``surfsense_defaults`` — single ``allow */*`` rule. Connector tools
   already self-gate via :func:`request_approval`, so the rule engine only
   needs to *deny* what the user has explicitly forbidden; the default
   ``ask`` fallback would otherwise double-prompt every safe read-only
   call.
2. ``subagent_rulesets`` — caller-supplied rulesets contributed by the
   consuming subagent. Each subagent passes its coded rules (KB:
   destructive-FS ``ask`` rules; connectors: per-tool ``allow``/``ask``)
   plus, when present, the user's persisted allow-list for that subagent.

Connector deny synthesis from ``new_chat._synthesize_connector_deny_rules``
is intentionally NOT replicated: the multi-agent orchestrator already
excludes entire subagents whose required connectors are missing
(``SUBAGENT_TO_REQUIRED_CONNECTOR_MAP``), so the per-tool deny pass is
redundant here.
"""

from __future__ import annotations

from collections.abc import Sequence

from langchain_core.tools import BaseTool

from app.agents.multi_agent_chat.shared.feature_flags import AgentFeatureFlags
from app.agents.multi_agent_chat.shared.permissions import Rule, Ruleset
from app.services.user_tool_allowlist import TrustedToolSaver

from .core import PermissionMiddleware

_SURFSENSE_DEFAULTS = Ruleset(
    rules=[Rule(permission="*", pattern="*", action="allow")],
    origin="surfsense_defaults",
)


def build_permission_mw(
    *,
    flags: AgentFeatureFlags,
    subagent_rulesets: list[Ruleset] | None = None,
    tools: Sequence[BaseTool] | None = None,
    trusted_tool_saver: TrustedToolSaver | None = None,
) -> PermissionMiddleware | None:
    """Return a configured :class:`PermissionMiddleware` or ``None`` when no work is needed.

    Args:
        flags: Feature toggles. ``enable_permission`` switches the engine on;
            ``disable_new_agent_stack`` overrides everything for safety.
        subagent_rulesets: Caller-supplied rulesets layered after the
            defaults. Subagents pass their own coded ruleset here (and,
            when present, the user's persisted allow-list for that
            subagent) so each subagent owns its own rule surface without
            aliasing a shared engine. Presence of any subagent ruleset
            forces the middleware on regardless of ``enable_permission`` —
            an explicit ``ask`` rule always asks.
        tools: Subagent tools used to decorate ``ask`` interrupts with
            FE-card metadata (description, MCP connector). Optional.
        trusted_tool_saver: Async callback invoked when an MCP tool's
            ``always`` decision lands; persists the user's preference to
            ``connector.config['trusted_tools']``. Optional.

    Returns:
        ``None`` when the engine has no rules to enforce
        (``enable_permission=False`` and no subagent rulesets); a
        configured middleware otherwise.
    """
    permission_enabled = flags.enable_permission and not flags.disable_new_agent_stack
    has_subagent_rulesets = bool(subagent_rulesets)
    if not (permission_enabled or has_subagent_rulesets):
        return None

    rulesets: list[Ruleset] = [_SURFSENSE_DEFAULTS]
    if subagent_rulesets:
        rulesets.extend(subagent_rulesets)
    tools_by_name = {t.name: t for t in (tools or [])}
    return PermissionMiddleware(
        rulesets=rulesets,
        tools_by_name=tools_by_name,
        trusted_tool_saver=trusted_tool_saver,
    )


__all__ = ["build_permission_mw"]
