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
from app.utils.text_spans import char_span_to_line_range

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


async def _resolve_doc_context(
    results: list[dict[str, Any]],
    *,
    search_space_id: int,
) -> tuple[dict[int, str], dict[int, str]]:
    """Resolve ``Document.id`` -> (canonical virtual path, source_markdown).

    ``source_markdown`` is the canonical body the chunk spans index into; the
    renderer uses it to turn a chunk's char span into a line range.
    """
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
        return {}, {}

    async with shielded_async_session() as session:
        index: PathIndex = await build_path_index(session, search_space_id)
        rows = await session.execute(
            select(
                Document.id, Document.folder_id, Document.source_markdown
            ).where(
                Document.search_space_id == search_space_id,
                Document.id.in_(doc_ids),
            )
        )
        folder_by_doc_id: dict[int, int | None] = {}
        bodies: dict[int, str] = {}
        for row in rows.all():
            folder_by_doc_id[row.id] = row.folder_id
            if row.source_markdown:
                bodies[row.id] = row.source_markdown

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
    return paths, bodies


def _citation_token(chunk: dict[str, Any], body: str | None, doc_id: int | None) -> str:
    """Ready-to-copy ``[citation:dID#Lstart-end]`` token, or '' without spans."""
    start = chunk.get("start_char")
    end = chunk.get("end_char")
    if (
        not body
        or not isinstance(doc_id, int)
        or not isinstance(start, int)
        or not isinstance(end, int)
    ):
        return ""
    start_line, end_line = char_span_to_line_range(body, start, end)
    return f"[citation:d{doc_id}#L{start_line}-{end_line}]"


def _render_passage(
    chunk: dict[str, Any], body: str | None, doc_id: int | None
) -> str | None:
    """Render one matched chunk as an indented passage tagged with its token."""
    content = (chunk.get("content") or "").strip()
    if not content:
        return None
    snippet = content[:_PER_DOC_SNIPPET_CHARS].strip()
    if len(content) > _PER_DOC_SNIPPET_CHARS:
        snippet += " ..."
    indented = snippet.replace("\n", "\n   ")
    token = _citation_token(chunk, body, doc_id)
    head = f"\n   {token}" if token else ""
    return f"{head}\n   {indented}"


def _matched_passages(
    doc: dict[str, Any], body: str | None, doc_id: int | None
) -> str:
    """Render the RRF-matched chunks; '' when none can be rendered."""
    by_id = {
        c.get("chunk_id"): c
        for c in (doc.get("chunks") or [])
        if isinstance(c, dict)
    }
    rendered: list[str] = []
    for chunk_id in doc.get("matched_chunk_ids") or []:
        chunk = by_id.get(chunk_id)
        if chunk is None:
            continue
        passage = _render_passage(chunk, body, doc_id)
        if passage:
            rendered.append(passage)
    return "".join(rendered)


def _fallback_snippet(doc: dict[str, Any]) -> str:
    """Top-of-document preview, used only when no matched chunk is available."""
    content = (doc.get("content") or "").strip()
    if not content:
        return "\n   (no preview available; read the document for details)"
    snippet = content[:_PER_DOC_SNIPPET_CHARS].strip()
    if len(content) > _PER_DOC_SNIPPET_CHARS:
        snippet += " ..."
    return "\n   " + snippet.replace("\n", "\n   ")


def _format_hits(
    results: list[dict[str, Any]],
    *,
    paths: dict[int, str],
    bodies: dict[int, str],
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
        body = bodies.get(doc_id) if isinstance(doc_id, int) else None

        id_str = f"id={doc_id}, " if isinstance(doc_id, int) else ""
        header = f"\n{rank}. {title} ({id_str}type={doc_type}, score={score_str})" + (
            f"\n   path: {path}" if path else ""
        )

        passages = _matched_passages(doc, body, doc_id if isinstance(doc_id, int) else None)
        entry = header + (passages or _fallback_snippet(doc))
        if total + len(entry) > _MAX_TOTAL_CHARS:
            lines.append("\n<!-- additional matches truncated to fit context -->")
            break
        lines.append(entry)
        total += len(entry)

    lines.append(
        "\n\nTo cite a matched passage, copy its [citation:dID#Lstart-end] token "
        "verbatim. To quote more context or read the full document, delegate to "
        "the knowledge_base specialist with `task` using the path above."
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

        paths, bodies = await _resolve_doc_context(results, search_space_id=_space_id)
        rendered = _format_hits(
            results, paths=paths, bodies=bodies, query=cleaned_query
        )
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
