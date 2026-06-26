"""On-demand ``search_knowledge_base`` knowledge_base-subagent tool (citation-spine RAG).

The knowledge_base subagent calls this when it needs hybrid semantic + keyword
retrieval over the user's indexed knowledge base. The tool runs one hybrid
search, renders the matched passages as a ``<retrieved_context>`` block whose
passages carry server-assigned ``[n]`` labels, and persists the conversation's
``CitationRegistry`` onto graph state so the ``[n]`` -> ``[citation:<payload>]``
normalizer can resolve them after the turn. The registry merges across the
subagent boundary (reducer-backed, forwarded by ``task``/``ask_knowledge_base``).
"""

from __future__ import annotations

import time
from typing import Annotated, Any

from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.multi_agent_chat.shared.citations import load_registry
from app.agents.chat.multi_agent_chat.shared.retrieval import SearchScope, build_context
from app.agents.chat.multi_agent_chat.shared.retrieval.hybrid_search import (
    search_chunks,
)
from app.agents.chat.multi_agent_chat.shared.state.filesystem_state import (
    SurfSenseFilesystemState,
)
from app.agents.chat.runtime.references import referenced_document_ids
from app.db import shielded_async_session
from app.utils.perf import get_perf_logger

_perf_log = get_perf_logger()

_DEFAULT_TOP_K = 5
_MAX_TOP_K = 20

_TOOL_DESCRIPTION = (
    "Search the user's knowledge base (their indexed documents, files, and "
    "connector content) for passages relevant to a query, using hybrid "
    "semantic + keyword retrieval.\n\n"
    "Use this FIRST to ground any factual or informational answer about the "
    "user's own documents, notes, or connected sources. It returns a "
    "<retrieved_context> block: each matched passage is labelled [n]. Cite a "
    "passage by writing that [n] after the statement it supports.\n\n"
    "Write a focused, specific query containing the concrete entities, "
    "acronyms, people, projects, or terms you are looking for."
)


def _search_types(
    available_connectors: list[str] | None,
    available_document_types: list[str] | None,
) -> tuple[str, ...] | None:
    """Merge connector + document-type filters into a scope; ``None`` if unrestricted."""
    types: set[str] = set()
    if available_document_types:
        types.update(available_document_types)
    if available_connectors:
        types.update(available_connectors)
    return tuple(sorted(types)) or None


def _resolve_mention_pins(
    runtime: ToolRuntime[None, SurfSenseFilesystemState],
) -> tuple[list[int] | None, list[int] | None]:
    """Read the turn's ``@``-mention pins, preferring state over context.

    On a subagent graph the pins arrive via forwarded **state** (the ``task``
    tool copies them off the main ``runtime.context`` since subagents have no
    ``context_schema``). On the main graph — or any future direct invocation
    with ``context=`` — they arrive via ``runtime.context``. State wins when
    both are present; context is the fallback.
    """
    state = getattr(runtime, "state", None) or {}
    document_ids = state.get("mentioned_document_ids")
    folder_ids = state.get("mentioned_folder_ids")
    if document_ids or folder_ids:
        return document_ids or None, folder_ids or None
    ctx = getattr(runtime, "context", None)
    return (
        getattr(ctx, "mentioned_document_ids", None),
        getattr(ctx, "mentioned_folder_ids", None),
    )


async def _build_search_scope(
    session: AsyncSession,
    *,
    workspace_id: int,
    document_types: tuple[str, ...] | None,
    runtime: ToolRuntime[None, SurfSenseFilesystemState],
) -> SearchScope:
    """Assemble the retrieval scope: workspace document-type filter + @-mention pins."""
    mentioned_document_ids, mentioned_folder_ids = _resolve_mention_pins(runtime)
    document_ids = await referenced_document_ids(
        session,
        workspace_id=workspace_id,
        document_ids=mentioned_document_ids,
        folder_ids=mentioned_folder_ids,
    )
    return SearchScope(
        document_types=document_types,
        document_ids=document_ids or None,
    )


def create_search_knowledge_base_tool(
    *,
    workspace_id: int,
    available_connectors: list[str] | None = None,
    available_document_types: list[str] | None = None,
) -> BaseTool:
    """Factory for the on-demand ``search_knowledge_base`` tool."""

    _space_id = workspace_id
    _document_types = _search_types(available_connectors, available_document_types)

    async def _impl(
        query: Annotated[
            str,
            "Focused search query with the concrete entities/terms to look for.",
        ],
        runtime: ToolRuntime[None, SurfSenseFilesystemState],
        top_k: Annotated[
            int,
            "Maximum number of documents to return (default 5).",
        ] = _DEFAULT_TOP_K,
    ) -> Command | str:
        cleaned_query = (query or "").strip()
        if not cleaned_query:
            return "Error: provide a non-empty search query."

        clamped_top_k = min(max(1, top_k), _MAX_TOP_K)
        registry = load_registry(getattr(runtime, "state", None))

        t0 = time.perf_counter()
        async with shielded_async_session() as session:
            scope = await _build_search_scope(
                session,
                workspace_id=_space_id,
                document_types=_document_types,
                runtime=runtime,
            )
            hits = await search_chunks(
                session,
                workspace_id=_space_id,
                query=cleaned_query,
                scope=scope,
                top_k=clamped_top_k,
            )
            rendered = build_context(cleaned_query, hits, registry)

        _perf_log.info(
            "[search_knowledge_base] tool query=%r docs=%d in %.3fs",
            cleaned_query[:60],
            len(hits),
            time.perf_counter() - t0,
        )

        if rendered is None:
            return (
                f"No knowledge-base matches found for query: {cleaned_query!r}.\n"
                "Tell the user nothing relevant was found in their workspace, or "
                "try a different query."
            )

        update: dict[str, Any] = {
            "messages": [
                ToolMessage(content=rendered, tool_call_id=runtime.tool_call_id)
            ],
            "citation_registry": registry,
        }
        return Command(update=update)

    return StructuredTool.from_function(
        name="search_knowledge_base",
        description=_TOOL_DESCRIPTION,
        coroutine=_impl,
    )
