"""Middleware list shared by the full and read-only knowledge_base compiles.

The KB-owned :class:`PermissionMiddleware` slot is what enforces
"ask before destructive FS op" for KB tools.
"""

from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel

from app.agents.multi_agent_chat.middleware.shared.anthropic_cache import (
    build_anthropic_cache_mw,
)
from app.agents.multi_agent_chat.middleware.shared.compaction import (
    build_compaction_mw,
)
from app.agents.multi_agent_chat.middleware.shared.filesystem import (
    build_filesystem_mw,
)
from app.agents.multi_agent_chat.middleware.shared.kb_context_projection import (
    build_kb_context_projection_mw,
)
from app.agents.multi_agent_chat.middleware.shared.patch_tool_calls import (
    build_patch_tool_calls_mw,
)
from app.agents.multi_agent_chat.middleware.shared.permissions import (
    build_permission_mw,
)
from app.agents.new_chat.feature_flags import AgentFeatureFlags
from app.agents.new_chat.filesystem_selection import FilesystemMode
from app.agents.new_chat.permissions import Ruleset


def _kb_user_allowlist(
    dependencies: dict[str, Any], subagent_name: str
) -> Ruleset | None:
    """Return the user's persisted allow-rules for ``subagent_name`` if any.

    KB does not currently expose an "Always Allow" UI surface (the FE
    button is MCP-only today), but the wiring is symmetrical with the
    connector subagents so that adding KB trust later is a one-line
    backend change.
    """
    by_subagent = dependencies.get("user_allowlist_by_subagent") or {}
    user_allowlist = by_subagent.get(subagent_name)
    if isinstance(user_allowlist, Ruleset) and user_allowlist.rules:
        return user_allowlist
    return None


def build_kb_middleware(
    *,
    llm: BaseChatModel,
    dependencies: dict[str, Any],
    middleware_stack: dict[str, Any] | None,
    read_only: bool,
    subagent_name: str,
    ruleset: Ruleset | None = None,
) -> list[Any]:
    """Compose the KB subagent's middleware list.

    Args:
        subagent_name: Identity of the subagent being built (e.g.
            ``"knowledge_base"``, ``"knowledge_base_readonly"``). Used to
            look up the user's persistent allow-list bucket in
            ``dependencies["user_allowlist_by_subagent"]``.
        ruleset: The KB-owned permission ruleset (typically the
            destructive-FS ``ask`` rules). When provided, a dedicated
            :class:`PermissionMiddleware` is appended so KB enforces
            approval at the rule layer. The user's persistent allow-list
            for ``subagent_name`` is layered after ``ruleset`` so user
            ``allow`` rules override coded ``ask`` rules via
            last-match-wins.
    """
    mws = middleware_stack or {}
    filesystem_mode: FilesystemMode = dependencies["filesystem_mode"]
    flags: AgentFeatureFlags | None = dependencies.get("flags")
    resilience_mws = [
        m
        for m in (
            mws.get("retry"),
            mws.get("fallback"),
            mws.get("model_call_limit"),
            mws.get("tool_call_limit"),
        )
        if m is not None
    ]
    permission_mw = None
    if ruleset is not None and flags is not None:
        rulesets: list[Ruleset] = [ruleset]
        user_allowlist = _kb_user_allowlist(dependencies, subagent_name)
        if user_allowlist is not None:
            rulesets.append(user_allowlist)
        permission_mw = build_permission_mw(
            flags=flags,
            subagent_rulesets=rulesets,
            trusted_tool_saver=dependencies.get("trusted_tool_saver"),
        )
    return [
        mws["todos"],
        build_kb_context_projection_mw(),
        build_filesystem_mw(
            backend_resolver=dependencies["backend_resolver"],
            filesystem_mode=filesystem_mode,
            search_space_id=dependencies["search_space_id"],
            user_id=dependencies.get("user_id"),
            thread_id=dependencies.get("thread_id"),
            read_only=read_only,
        ),
        build_compaction_mw(llm),
        build_patch_tool_calls_mw(),
        *([permission_mw] if permission_mw is not None else []),
        *resilience_mws,
        build_anthropic_cache_mw(),
    ]
