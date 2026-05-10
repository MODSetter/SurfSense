"""General-purpose subagent for the multi-agent main agent."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from deepagents import SubAgent
from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware
from deepagents.middleware.subagents import GENERAL_PURPOSE_SUBAGENT
from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from app.agents.multi_agent_chat.middleware.shared.anthropic_cache import (
    build_anthropic_cache_mw,
)
from app.agents.multi_agent_chat.middleware.shared.compaction import (
    build_compaction_mw,
)
from app.agents.multi_agent_chat.middleware.shared.file_intent import (
    build_file_intent_mw,
)
from app.agents.multi_agent_chat.middleware.shared.filesystem import (
    build_filesystem_mw,
)
from app.agents.multi_agent_chat.middleware.shared.patch_tool_calls import (
    build_patch_tool_calls_mw,
)
from app.agents.multi_agent_chat.middleware.shared.permissions import (
    PermissionContext,
)
from app.agents.multi_agent_chat.middleware.shared.resilience import (
    ResilienceBundle,
)
from app.agents.multi_agent_chat.middleware.shared.todos import build_todos_mw
from app.agents.new_chat.filesystem_selection import FilesystemMode
from app.agents.new_chat.middleware import MemoryInjectionMiddleware

NAME = "general-purpose"


def build_subagent(
    *,
    llm: BaseChatModel,
    tools: Sequence[BaseTool],
    backend_resolver: Any,
    filesystem_mode: FilesystemMode,
    search_space_id: int,
    user_id: str | None,
    thread_id: int | None,
    permissions: PermissionContext,
    resilience: ResilienceBundle,
    memory_mw: MemoryInjectionMiddleware,
) -> SubAgent:
    """Deny + resilience inserts encapsulated here so the orchestrator never mutates the list."""
    middleware: list[Any] = [
        build_todos_mw(),
        memory_mw,
        build_file_intent_mw(llm),
        build_filesystem_mw(
            backend_resolver=backend_resolver,
            filesystem_mode=filesystem_mode,
            search_space_id=search_space_id,
            user_id=user_id,
            thread_id=thread_id,
        ),
        build_compaction_mw(llm),
        build_patch_tool_calls_mw(),
        build_anthropic_cache_mw(),
    ]

    if permissions.subagent_deny_mw is not None:
        patch_idx = next(
            (
                i
                for i, m in enumerate(middleware)
                if isinstance(m, PatchToolCallsMiddleware)
            ),
            len(middleware),
        )
        middleware.insert(patch_idx, permissions.subagent_deny_mw)

    resilience_mws = resilience.as_list()
    if resilience_mws:
        cache_idx = next(
            (
                i
                for i, m in enumerate(middleware)
                if isinstance(m, AnthropicPromptCachingMiddleware)
            ),
            len(middleware),
        )
        for offset, mw in enumerate(resilience_mws):
            middleware.insert(cache_idx + offset, mw)

    spec: dict[str, Any] = {
        **GENERAL_PURPOSE_SUBAGENT,
        "model": llm,
        "tools": tools,
        "middleware": middleware,
    }
    if permissions.general_purpose_interrupt_on:
        spec["interrupt_on"] = permissions.general_purpose_interrupt_on
    return cast(SubAgent, spec)
