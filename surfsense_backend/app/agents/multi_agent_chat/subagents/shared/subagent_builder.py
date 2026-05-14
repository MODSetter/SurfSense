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
from app.agents.new_chat.feature_flags import AgentFeatureFlags
from app.agents.new_chat.permissions import Ruleset


def pack_subagent(
    *,
    name: str,
    description: str,
    system_prompt: str,
    tools: list[BaseTool],
    ruleset: Ruleset,
    flags: AgentFeatureFlags,
    model: BaseChatModel | None = None,
    middleware_stack: dict[str, Any] | None = None,
) -> SurfSenseSubagentSpec:
    """Pack the route-local pieces into one sub-agent spec + its Ruleset.

    Tool gating is uniformly performed by a per-subagent
    :class:`PermissionMiddleware` built from the subagent's own
    ``ruleset`` (layered on top of the SurfSense defaults). The shared
    ``permission`` slot from ``middleware_stack`` is dropped so each
    subagent owns its own rule surface.
    """
    if not system_prompt.strip():
        msg = f"Subagent {name!r}: system_prompt is empty"
        raise ValueError(msg)

    per_subagent_perm = build_permission_mw(flags=flags, extra_rulesets=[ruleset])
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
