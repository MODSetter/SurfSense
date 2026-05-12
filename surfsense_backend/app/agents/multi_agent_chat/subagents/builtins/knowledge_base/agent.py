"""`knowledge_base` route: ``SubAgent`` spec for the SurfSense KB specialist.

The KB subagent owns the `/documents/` workspace: reading, writing, editing,
searching, and organising user documents. It shares the orchestrator's
``workspace_tree_text`` and ``kb_priority`` via state and re-emits them as
SystemMessages through the projection middleware (no extra DB / LLM calls).
"""

from __future__ import annotations

from typing import Any, cast

from deepagents import SubAgent
from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware
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
from app.agents.multi_agent_chat.middleware.shared.resilience import (
    ResilienceBundle,
)
from app.agents.multi_agent_chat.middleware.shared.todos import build_todos_mw
from app.agents.multi_agent_chat.subagents.shared.md_file_reader import (
    read_md_file,
)
from app.agents.new_chat.filesystem_selection import FilesystemMode

from .tools.index import destructive_fs_interrupt_on

NAME = "knowledge_base"


def build_subagent(
    *,
    llm: BaseChatModel,
    backend_resolver: Any,
    filesystem_mode: FilesystemMode,
    search_space_id: int,
    user_id: str | None,
    thread_id: int | None,
    resilience: ResilienceBundle,
) -> SubAgent:
    """Resilience inserts encapsulated here so the orchestrator never mutates the list."""
    description = read_md_file(__package__, "description").strip()
    if not description:
        description = (
            "Handles knowledge-base reads, writes, edits, and organisation."
        )
    prompt_stem = (
        "system_prompt_cloud"
        if filesystem_mode == FilesystemMode.CLOUD
        else "system_prompt_desktop"
    )
    system_prompt = read_md_file(__package__, prompt_stem).strip()

    middleware: list[Any] = [
        build_todos_mw(),
        build_kb_context_projection_mw(),
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
        "name": NAME,
        "description": description,
        "system_prompt": system_prompt,
        "model": llm,
        "tools": [],
        "middleware": middleware,
        "interrupt_on": destructive_fs_interrupt_on(),
    }
    return cast(SubAgent, spec)
