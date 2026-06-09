"""On-demand ``search_knowledge_base`` main-agent tool (OpenCode-style lazy RAG).

The main agent no longer receives eagerly pre-injected KB context on every
turn (see :class:`KnowledgePriorityMiddleware`, now gated off by default).
Instead it calls this tool only when it decides it needs knowledge-base
content. The tool runs a single hybrid search (embed + DB search, ~0.5s),
formats the top matches for the model, and writes ``kb_matched_chunk_ids``
into graph state so matched-section highlighting is preserved when the agent
later reads a document via ``task(knowledge_base)``.
"""

from __future__ import annotations

import time
from typing import Annotated, Any

from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.types import Command
from sqlalchemy import select

from app.agents.chat.multi_agent_chat.shared.middleware.knowledge_search import (
    search_knowledge_base as _hybrid_search_kb,
)
from app.agents.chat.multi_agent_chat.shared.state.filesystem_state import (
    SurfSenseFilesystemState,
)
from app.agents.chat.runtime.path_resolver import (
    PathIndex,
    build_path_index,
    doc_to_virtual_path,
)
from app.db import Document, shielded_async_session
from app.utils.perf import get_perf_logger

_perf_log = get_perf_logger()

_DEFAULT_TOP_K = 5
_MAX_TOP_K = 20
_PER_DOC_SNIPPET_CHARS = 1200
_MAX_TOTAL_CHARS = 16_000

_TOOL_DESCRIPTION = (
    "Search the user's knowledge base (their indexed documents, files, and "
    "connector content) for passages relevant to a query, using hybrid "
    "semantic + keyword retrieval.\n\n"
    "Use this FIRST to ground any factual or informational answer about the "
    "user's own documents, notes, or connected sources. The workspace tree "
    "shows which files exist; this tool pulls the actual relevant content. "
    "Each hit returns the document's virtual path, a relevance score, and the "
    "matched snippets. If you need a document's full text, delegate a read to "
    "the knowledge_base specialist via `task` using the returned path.\n\n"
    "Write a focused, specific query containing the concrete entities, "
    "acronyms, people, projects, or terms you are looking for."
)


async def _resolve_virtual_paths(
    results: list[dict[str, Any]],
    *,
    search_space_id: int,
) -> dict[int, str]:
    """Resolve ``Document.id`` -> canonical virtual path for the search hits."""
    doc_ids = [
        doc_id
        for doc_id in (
            (doc.get("document") or {}).get("id")
            for doc in results
            if isinstance(doc, dict)
        )
        if isinstance(doc_id, int)
    ]
    if not doc_ids:
        return {}

    async with shielded_async_session() as session:
        index: PathIndex = await build_path_index(session, search_space_id)
        folder_rows = await session.execute(
            select(Document.id, Document.folder_id).where(
                Document.search_space_id == search_space_id,
                Document.id.in_(doc_ids),
            )
        )
        folder_by_doc_id = {row.id: row.folder_id for row in folder_rows.all()}

    paths: dict[int, str] = {}
    for doc in results:
        doc_meta = doc.get("document") or {}
        doc_id = doc_meta.get("id")
        if not isinstance(doc_id, int):
            continue
        folder_id = folder_by_doc_id.get(doc_id, doc_meta.get("folder_id"))
        paths[doc_id] = doc_to_virtual_path(
            doc_id=doc_id,
            title=str(doc_meta.get("title") or "untitled"),
            folder_id=folder_id if isinstance(folder_id, int) else None,
            index=index,
        )
    return paths


def _format_hits(
    results: list[dict[str, Any]],
    *,
    paths: dict[int, str],
    query: str,
) -> str:
    """Render search hits as a compact, model-readable block."""
    if not results:
        return (
            f"No knowledge-base matches found for query: {query!r}.\n"
            "Tell the user nothing relevant was found in their workspace, or "
            "try a different query."
        )

    lines: list[str] = [f"<knowledge_base_results query={query!r}>"]
    total = len(lines[0])
    for rank, doc in enumerate(results, start=1):
        doc_meta = doc.get("document") or {}
        doc_id = doc_meta.get("id")
        title = str(doc_meta.get("title") or "untitled")
        doc_type = doc_meta.get("document_type") or doc.get("source") or "document"
        score = doc.get("score")
        score_str = f"{score:.3f}" if isinstance(score, int | float) else "n/a"
        path = paths.get(doc_id) if isinstance(doc_id, int) else None

        header = f"\n{rank}. {title} (type={doc_type}, score={score_str})" + (
            f"\n   path: {path}" if path else ""
        )

        content = (doc.get("content") or "").strip()
        if content:
            snippet = content[:_PER_DOC_SNIPPET_CHARS].strip()
            if len(content) > _PER_DOC_SNIPPET_CHARS:
                snippet += " ..."
            body = "\n   " + snippet.replace("\n", "\n   ")
        else:
            body = "\n   (no preview available; read the document for details)"

        entry = header + body
        if total + len(entry) > _MAX_TOTAL_CHARS:
            lines.append("\n<!-- additional matches truncated to fit context -->")
            break
        lines.append(entry)
        total += len(entry)

    lines.append(
        "\n\nTo read a full document, delegate to the knowledge_base specialist "
        "with `task`, referencing the path above."
    )
    lines.append("\n</knowledge_base_results>")
    return "".join(lines)


def _matched_chunk_ids(results: list[dict[str, Any]]) -> dict[int, list[int]]:
    """Extract ``Document.id`` -> matched chunk ids for state hand-off."""
    matched: dict[int, list[int]] = {}
    for doc in results:
        doc_id = (doc.get("document") or {}).get("id")
        if not isinstance(doc_id, int):
            continue
        chunk_ids = doc.get("matched_chunk_ids") or []
        normalized = [int(cid) for cid in chunk_ids if isinstance(cid, int | str)]
        if normalized:
            matched[doc_id] = normalized
    return matched


def create_search_knowledge_base_tool(
    *,
    search_space_id: int,
    available_connectors: list[str] | None = None,
    available_document_types: list[str] | None = None,
) -> BaseTool:
    """Factory for the on-demand ``search_knowledge_base`` tool."""

    _space_id = search_space_id
    _connectors = available_connectors
    _doc_types = available_document_types

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
        t0 = time.perf_counter()
        results = await _hybrid_search_kb(
            query=cleaned_query,
            search_space_id=_space_id,
            available_connectors=_connectors,
            available_document_types=_doc_types,
            top_k=clamped_top_k,
        )

        paths = await _resolve_virtual_paths(results, search_space_id=_space_id)
        rendered = _format_hits(results, paths=paths, query=cleaned_query)
        matched = _matched_chunk_ids(results)

        _perf_log.info(
            "[search_knowledge_base] tool query=%r results=%d chars=%d in %.3fs",
            cleaned_query[:60],
            len(results),
            len(rendered),
            time.perf_counter() - t0,
        )

        update: dict[str, Any] = {
            "messages": [
                ToolMessage(content=rendered, tool_call_id=runtime.tool_call_id)
            ],
        }
        if matched:
            update["kb_matched_chunk_ids"] = matched
        return Command(update=update)

    return StructuredTool.from_function(
        name="search_knowledge_base",
        description=_TOOL_DESCRIPTION,
        coroutine=_impl,
    )
