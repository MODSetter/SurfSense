"""Middleware list shared by the full and read-only knowledge_base compiles."""

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
from app.agents.new_chat.filesystem_selection import FilesystemMode


def build_kb_middleware(
    *,
    llm: BaseChatModel,
    dependencies: dict[str, Any],
    middleware_stack: dict[str, Any] | None,
    read_only: bool,
) -> list[Any]:
    mws = middleware_stack or {}
    filesystem_mode: FilesystemMode = dependencies["filesystem_mode"]
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
        *resilience_mws,
        build_anthropic_cache_mw(),
    ]
