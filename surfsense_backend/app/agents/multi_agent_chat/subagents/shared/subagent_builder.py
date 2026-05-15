"""Build delegated sub-agent specs from route-local pieces."""

from __future__ import annotations

from typing import Any, cast

from deepagents import SubAgent
from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from app.agents.multi_agent_chat.middleware.shared.permissions import (
    build_permission_mw,
)
from app.agents.multi_agent_chat.subagents.shared.spec import SurfSenseSubagentSpec
from app.agents.new_chat.permissions import Ruleset


def _user_allowlist_for(
    dependencies: dict[str, Any], subagent_name: str
) -> Ruleset | None:
    """Return the user's persisted allow-rules for ``subagent_name`` if any.

    Populated by the agent factory from
    :func:`app.services.user_tool_allowlist.fetch_user_allowlist_rulesets`.
    Returning ``None`` is the common case (fresh accounts, non-MCP
    subagents, or no "Always Allow" interactions yet).
    """
    by_subagent = dependencies.get("user_allowlist_by_subagent") or {}
    user_allowlist = by_subagent.get(subagent_name)
    if isinstance(user_allowlist, Ruleset) and user_allowlist.rules:
        return user_allowlist
    return None


def pack_subagent(
    *,
    name: str,
    description: str,
    system_prompt: str,
    tools: list[BaseTool],
    ruleset: Ruleset,
    dependencies: dict[str, Any],
    model: BaseChatModel | None = None,
    middleware_stack: dict[str, Any] | None = None,
) -> SurfSenseSubagentSpec:
    """Pack the route-local pieces into one sub-agent spec + its Ruleset.

    Tool gating is uniformly performed by a per-subagent
    :class:`PermissionMiddleware`. Three rule layers are evaluated
    earliest-to-latest (last match wins):

    1. SurfSense defaults — single ``allow */*`` rule (added by
       :func:`build_permission_mw`).
    2. ``ruleset`` — the subagent's coded approval rules (e.g. KB's
       destructive-FS ``ask`` rules, connector ``ask`` writes).
    3. The user's persisted allow-list for this subagent — pulled from
       ``dependencies['user_allowlist_by_subagent'][name]``. User
       ``allow`` rules layered last override coded ``ask`` rules,
       implementing the "Always Allow" UX without re-asking on the
       next turn.

    The shared ``permission`` slot from ``middleware_stack`` is dropped
    so each subagent owns its own rule surface and cannot accidentally
    share state with the main agent's permission middleware.
    """
    if not system_prompt.strip():
        msg = f"Subagent {name!r}: system_prompt is empty"
        raise ValueError(msg)

    flags = dependencies["flags"]
    user_allowlist = _user_allowlist_for(dependencies, name)
    subagent_rulesets: list[Ruleset] = [ruleset]
    if user_allowlist is not None:
        subagent_rulesets.append(user_allowlist)
    per_subagent_perm = build_permission_mw(
        flags=flags, subagent_rulesets=subagent_rulesets, tools=tools
    )

    prepended: list[Any] = []
    for slot, mw in (middleware_stack or {}).items():
        if mw is None:
            continue
        if slot == "permission":
            continue
        prepended.append(mw)
    if per_subagent_perm is not None:
        prepended.append(per_subagent_perm)
    middleware: list[Any] = [*prepended, PatchToolCallsMiddleware()]
    spec_dict: dict[str, Any] = {
        "name": name,
        "description": description,
        "system_prompt": system_prompt,
        "tools": tools,
        "middleware": middleware,
    }
    if model is not None:
        spec_dict["model"] = model
    return SurfSenseSubagentSpec(spec=cast(SubAgent, spec_dict), ruleset=ruleset)
