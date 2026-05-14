"""Construction recipe for :class:`PermissionMiddleware` shared across stacks.

Single source of truth used by both the main-agent stack and every subagent
stack. Rule layers are evaluated earliest-to-latest (last match wins,
matching OpenCode's ``permission/index.ts`` evaluation order):

1. ``surfsense_defaults`` — single ``allow */*`` rule. Connector tools
   already self-gate via :func:`request_approval`, so the rule engine only
   needs to *deny* what the user has explicitly forbidden; the default
   ``ask`` fallback would otherwise double-prompt every safe read-only
   call.
2. ``extra_rulesets`` — caller-supplied rulesets. Each subagent
   contributes its own (KB: destructive-FS ``ask`` rules; connectors:
   per-tool ``allow``/``ask``).

Connector deny synthesis from ``new_chat._synthesize_connector_deny_rules``
is intentionally NOT replicated: the multi-agent orchestrator already
excludes entire subagents whose required connectors are missing
(``SUBAGENT_TO_REQUIRED_CONNECTOR_MAP``), so the per-tool deny pass is
redundant here.
"""

from __future__ import annotations

from app.agents.new_chat.feature_flags import AgentFeatureFlags
from app.agents.new_chat.permissions import Rule, Ruleset

from .core import PermissionMiddleware

_SURFSENSE_DEFAULTS = Ruleset(
    rules=[Rule(permission="*", pattern="*", action="allow")],
    origin="surfsense_defaults",
)


def build_permission_mw(
    *,
    flags: AgentFeatureFlags,
    extra_rulesets: list[Ruleset] | None = None,
) -> PermissionMiddleware | None:
    """Return a configured :class:`PermissionMiddleware` or ``None`` when no work is needed.

    Args:
        flags: Feature toggles. ``enable_permission`` switches the engine on;
            ``disable_new_agent_stack`` overrides everything for safety.
        extra_rulesets: Caller-supplied rulesets layered after the defaults.
            Subagents pass their own ruleset here so each subagent owns its
            rules without aliasing a shared engine. Presence of any extra
            ruleset forces the middleware on regardless of
            ``enable_permission`` — an explicit ``ask`` rule always asks.

    Returns:
        ``None`` when the engine has no rules to enforce
        (``enable_permission=False`` and no extras); a configured middleware
        otherwise.
    """
    permission_enabled = flags.enable_permission and not flags.disable_new_agent_stack
    has_extras = bool(extra_rulesets)
    if not (permission_enabled or has_extras):
        return None

    rulesets: list[Ruleset] = [_SURFSENSE_DEFAULTS]
    if extra_rulesets:
        rulesets.extend(extra_rulesets)
    return PermissionMiddleware(rulesets=rulesets)


__all__ = ["build_permission_mw"]
