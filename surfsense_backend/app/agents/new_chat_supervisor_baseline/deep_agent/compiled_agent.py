"""Compile a minimal supervisor graph: no bound tools, no tool-injecting middleware."""

from __future__ import annotations

from collections.abc import Sequence

from deepagents import __version__ as deepagents_version
from deepagents.backends import StateBackend
from langchain.agents import create_agent
from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.types import Checkpointer

from app.agents.new_chat.context import SurfSenseContextSchema
from app.agents.new_chat.feature_flags import AgentFeatureFlags
from app.agents.new_chat.filesystem_selection import FilesystemMode
from app.agents.new_chat.middleware import (
    AnonymousDocumentMiddleware,
    FileIntentMiddleware,
    KnowledgeBasePersistenceMiddleware,
    KnowledgePriorityMiddleware,
    KnowledgeTreeMiddleware,
    MemoryInjectionMiddleware,
    create_surfsense_compaction_middleware,
)
from app.db import ChatVisibility


def build_compiled_agent_blocking(
    *,
    llm: BaseChatModel,
    tools: Sequence[BaseTool],
    final_system_prompt: str,
    filesystem_mode: FilesystemMode,
    search_space_id: int,
    user_id: str | None,
    thread_id: int | None,
    visibility: ChatVisibility,
    anon_session_id: str | None,
    available_connectors: list[str] | None,
    available_document_types: list[str] | None,
    mentioned_document_ids: list[int] | None,
    flags: AgentFeatureFlags,
    checkpointer: Checkpointer,
):
    """Build middleware + compile graph synchronously (typically ``asyncio.to_thread``).

    Intentionally excludes registry tools (``tools`` should be ``[]``), SubAgent/task,
    filesystem/todo/skills middleware, and tool-centric hygiene (repair, dedup, permission).
    """
    _ = flags  # retained for API parity with callers; stack is fixed minimal for now

    _memory_middleware = MemoryInjectionMiddleware(
        user_id=user_id,
        search_space_id=search_space_id,
        thread_visibility=visibility,
    )

    summarization_mw = create_surfsense_compaction_middleware(llm, StateBackend)

    deepagent_middleware = [
        _memory_middleware,
        AnonymousDocumentMiddleware(anon_session_id=anon_session_id)
        if filesystem_mode == FilesystemMode.CLOUD
        else None,
        KnowledgeTreeMiddleware(
            search_space_id=search_space_id,
            filesystem_mode=filesystem_mode,
            llm=llm,
        )
        if filesystem_mode == FilesystemMode.CLOUD
        else None,
        KnowledgePriorityMiddleware(
            llm=llm,
            search_space_id=search_space_id,
            filesystem_mode=filesystem_mode,
            available_connectors=available_connectors,
            available_document_types=available_document_types,
            mentioned_document_ids=mentioned_document_ids,
        ),
        FileIntentMiddleware(llm=llm),
        KnowledgeBasePersistenceMiddleware(
            search_space_id=search_space_id,
            created_by_id=user_id,
            filesystem_mode=filesystem_mode,
            thread_id=thread_id,
        )
        if filesystem_mode == FilesystemMode.CLOUD
        else None,
        summarization_mw,
        AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore"),
    ]
    deepagent_middleware = [m for m in deepagent_middleware if m is not None]

    agent = create_agent(
        llm,
        system_prompt=final_system_prompt,
        tools=list(tools),
        middleware=deepagent_middleware,
        context_schema=SurfSenseContextSchema,
        checkpointer=checkpointer,
    )
    return agent.with_config(
        {
            "recursion_limit": 10_000,
            "metadata": {
                "ls_integration": "deepagents",
                "versions": {"deepagents": deepagents_version},
            },
        }
    )
