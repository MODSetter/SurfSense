"""Build delegated sub-agent specs from route-local pieces."""

from __future__ import annotations

from typing import Any, cast

from deepagents import SubAgent
from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from app.agents.new_chat.middleware import DedupHITLToolCallsMiddleware


def pack_subagent(
    *,
    name: str,
    description: str,
    system_prompt: str,
    tools: list[BaseTool],
    model: BaseChatModel | None = None,
    middleware_stack: dict[str, Any] | None = None,
    interrupt_on: dict[str, bool] | None = None,
) -> SubAgent:
    """Pack the route-local pieces passed in into one sub-agent spec.

    ``middleware_stack`` is the shared subagent middleware stack (see
    ``build_subagent_middleware_stack``). Every non-``None`` value is
    prepended to this subagent's middleware list in insertion order.
    """
    if not system_prompt.strip():
        msg = f"Subagent {name!r}: system_prompt is empty"
        raise ValueError(msg)

    prepended = [m for m in (middleware_stack or {}).values() if m is not None]
    middleware: list[Any] = [
        *prepended,
        PatchToolCallsMiddleware(),
        DedupHITLToolCallsMiddleware(agent_tools=tools),
    ]
    spec: dict[str, Any] = {
        "name": name,
        "description": description,
        "system_prompt": system_prompt,
        "tools": tools,
        "middleware": middleware,
    }
    if model is not None:
        spec["model"] = model
    if interrupt_on:
        spec["interrupt_on"] = interrupt_on
    return cast(SubAgent, spec)
