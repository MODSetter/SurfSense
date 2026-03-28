"""Knowledge-base pre-search middleware for the SurfSense new chat agent.

This middleware runs before the main agent loop and seeds a virtual filesystem
(`files` state) with relevant documents retrieved via hybrid search.  On each
turn the filesystem is *expanded* — new results merge with documents loaded
during prior turns — and a synthetic ``ls`` result is injected into the message
history so the LLM is immediately aware of the current filesystem structure.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from collections.abc import Sequence
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langgraph.runtime import Runtime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import NATIVE_TO_LEGACY_DOCTYPE, Document, Folder, shielded_async_session
from app.retriever.chunks_hybrid_search import ChucksHybridSearchRetriever
from app.utils.document_converters import embed_texts
from app.utils.perf import get_perf_logger

logger = logging.getLogger(__name__)
_perf_log = get_perf_logger()


def _extract_text_from_message(message: BaseMessage) -> str:
    """Extract plain text from a message content."""
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "\n".join(p for p in parts if p)
    return str(content)


def _safe_filename(value: str, *, fallback: str = "untitled.xml") -> str:
    """Convert arbitrary text into a filesystem-safe filename."""
    name = re.sub(r"[\\/:*?\"<>|]+", "_", value).strip()
    name = re.sub(r"\s+", " ", name)
    if not name:
        name = fallback
    if len(name) > 180:
        name = name[:180].rstrip()
    if not name.lower().endswith(".xml"):
        name = f"{name}.xml"
    return name


def _build_document_xml(
    document: dict[str, Any],
    matched_chunk_ids: set[int] | None = None,
) -> str:
    """Build citation-friendly XML with a ``<chunk_index>`` for smart seeking.

    The ``<chunk_index>`` at the top of each document lists every chunk with its
    line range inside ``<document_content>`` and flags chunks that directly
    matched the search query (``matched="true"``).  This lets the LLM jump
    straight to the most relevant section via ``read_file(offset=…, limit=…)``
    instead of reading sequentially from the start.
    """
    matched = matched_chunk_ids or set()

    doc_meta = document.get("document") or {}
    metadata = (doc_meta.get("metadata") or {}) if isinstance(doc_meta, dict) else {}
    document_id = doc_meta.get("id", document.get("document_id", "unknown"))
    document_type = doc_meta.get("document_type", document.get("source", "UNKNOWN"))
    title = doc_meta.get("title") or metadata.get("title") or "Untitled Document"
    url = (
        metadata.get("url") or metadata.get("source") or metadata.get("page_url") or ""
    )
    metadata_json = json.dumps(metadata, ensure_ascii=False)

    # --- 1. Metadata header (fixed structure) ---
    metadata_lines: list[str] = [
        "<document>",
        "<document_metadata>",
        f"  <document_id>{document_id}</document_id>",
        f"  <document_type>{document_type}</document_type>",
        f"  <title><![CDATA[{title}]]></title>",
        f"  <url><![CDATA[{url}]]></url>",
        f"  <metadata_json><![CDATA[{metadata_json}]]></metadata_json>",
        "</document_metadata>",
        "",
    ]

    # --- 2. Pre-build chunk XML strings to compute line counts ---
    chunks = document.get("chunks") or []
    chunk_entries: list[tuple[int | None, str]] = []  # (chunk_id, xml_string)
    if isinstance(chunks, list):
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            chunk_id = chunk.get("chunk_id") or chunk.get("id")
            chunk_content = str(chunk.get("content", "")).strip()
            if not chunk_content:
                continue
            if chunk_id is None:
                xml = f"  <chunk><![CDATA[{chunk_content}]]></chunk>"
            else:
                xml = f"  <chunk id='{chunk_id}'><![CDATA[{chunk_content}]]></chunk>"
            chunk_entries.append((chunk_id, xml))

    # --- 3. Compute line numbers for every chunk ---
    # Layout (1-indexed lines for read_file):
    #   metadata_lines          -> len(metadata_lines) lines
    #   <chunk_index>           -> 1 line
    #   index entries           -> len(chunk_entries) lines
    #   </chunk_index>          -> 1 line
    #   (empty line)            -> 1 line
    #   <document_content>      -> 1 line
    #   chunk xml lines…
    #   </document_content>     -> 1 line
    #   </document>             -> 1 line
    index_overhead = (
        1 + len(chunk_entries) + 1 + 1 + 1
    )  # tags + empty + <document_content>
    first_chunk_line = len(metadata_lines) + index_overhead + 1  # 1-indexed

    current_line = first_chunk_line
    index_entry_lines: list[str] = []
    for cid, xml_str in chunk_entries:
        num_lines = xml_str.count("\n") + 1
        end_line = current_line + num_lines - 1
        matched_attr = ' matched="true"' if cid is not None and cid in matched else ""
        if cid is not None:
            index_entry_lines.append(
                f'  <entry chunk_id="{cid}" lines="{current_line}-{end_line}"{matched_attr}/>'
            )
        else:
            index_entry_lines.append(
                f'  <entry lines="{current_line}-{end_line}"{matched_attr}/>'
            )
        current_line = end_line + 1

    # --- 4. Assemble final XML ---
    lines = metadata_lines.copy()
    lines.append("<chunk_index>")
    lines.extend(index_entry_lines)
    lines.append("</chunk_index>")
    lines.append("")
    lines.append("<document_content>")
    for _, xml_str in chunk_entries:
        lines.append(xml_str)
    lines.extend(["</document_content>", "</document>"])
    return "\n".join(lines)


async def _get_folder_paths(
    session: AsyncSession, search_space_id: int
) -> dict[int, str]:
    """Return a map of folder_id -> virtual folder path under /documents."""
    result = await session.execute(
        select(Folder.id, Folder.name, Folder.parent_id).where(
            Folder.search_space_id == search_space_id
        )
    )
    rows = result.all()
    by_id = {row.id: {"name": row.name, "parent_id": row.parent_id} for row in rows}

    cache: dict[int, str] = {}

    def resolve_path(folder_id: int) -> str:
        if folder_id in cache:
            return cache[folder_id]
        parts: list[str] = []
        cursor: int | None = folder_id
        visited: set[int] = set()
        while cursor is not None and cursor in by_id and cursor not in visited:
            visited.add(cursor)
            entry = by_id[cursor]
            parts.append(
                _safe_filename(str(entry["name"]), fallback="folder").removesuffix(
                    ".xml"
                )
            )
            cursor = entry["parent_id"]
        parts.reverse()
        path = "/documents/" + "/".join(parts) if parts else "/documents"
        cache[folder_id] = path
        return path

    for folder_id in by_id:
        resolve_path(folder_id)
    return cache


def _build_synthetic_ls(
    existing_files: dict[str, Any] | None,
    new_files: dict[str, Any],
) -> tuple[AIMessage, ToolMessage]:
    """Build a synthetic ls("/documents") tool-call + result for the LLM context.

    Paths are listed with *new* (rank-ordered) files first, then existing files
    that were already in state from prior turns.
    """
    merged: dict[str, Any] = {**(existing_files or {}), **new_files}
    doc_paths = [
        p for p, v in merged.items() if p.startswith("/documents/") and v is not None
    ]

    new_set = set(new_files)
    new_paths = [p for p in doc_paths if p in new_set]
    old_paths = [p for p in doc_paths if p not in new_set]
    ordered = new_paths + old_paths

    tool_call_id = f"auto_ls_{uuid.uuid4().hex[:12]}"
    ai_msg = AIMessage(
        content="",
        tool_calls=[{"name": "ls", "args": {"path": "/documents"}, "id": tool_call_id}],
    )
    tool_msg = ToolMessage(
        content=str(ordered) if ordered else "No documents found.",
        tool_call_id=tool_call_id,
    )
    return ai_msg, tool_msg


def _resolve_search_types(
    available_connectors: list[str] | None,
    available_document_types: list[str] | None,
) -> list[str] | None:
    """Build a flat list of document-type strings for the chunk retriever.

    Includes legacy equivalents from ``NATIVE_TO_LEGACY_DOCTYPE`` so that
    old documents indexed under Composio names are still found.

    Returns ``None`` when no filtering is desired (search all types).
    """
    types: set[str] = set()
    if available_document_types:
        types.update(available_document_types)
    if available_connectors:
        types.update(available_connectors)
    if not types:
        return None

    expanded: set[str] = set(types)
    for t in types:
        legacy = NATIVE_TO_LEGACY_DOCTYPE.get(t)
        if legacy:
            expanded.add(legacy)
    return list(expanded) if expanded else None


async def search_knowledge_base(
    *,
    query: str,
    search_space_id: int,
    available_connectors: list[str] | None = None,
    available_document_types: list[str] | None = None,
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """Run a single unified hybrid search against the knowledge base.

    Uses one ``ChucksHybridSearchRetriever`` call across all document types
    instead of fanning out per-connector.  This reduces the number of DB
    queries from ~10 to 2 (one RRF query + one chunk fetch).
    """
    if not query:
        return []

    [embedding] = embed_texts([query])

    doc_types = _resolve_search_types(available_connectors, available_document_types)
    retriever_top_k = min(top_k * 3, 30)

    async with shielded_async_session() as session:
        retriever = ChucksHybridSearchRetriever(session)
        results = await retriever.hybrid_search(
            query_text=query,
            top_k=retriever_top_k,
            search_space_id=search_space_id,
            document_type=doc_types,
            query_embedding=embedding.tolist(),
        )

    return results[:top_k]


async def build_scoped_filesystem(
    *,
    documents: Sequence[dict[str, Any]],
    search_space_id: int,
) -> dict[str, dict[str, str]]:
    """Build a StateBackend-compatible files dict from search results."""
    async with shielded_async_session() as session:
        folder_paths = await _get_folder_paths(session, search_space_id)
        doc_ids = [
            (doc.get("document") or {}).get("id")
            for doc in documents
            if isinstance(doc, dict)
        ]
        doc_ids = [doc_id for doc_id in doc_ids if isinstance(doc_id, int)]
        folder_by_doc_id: dict[int, int | None] = {}
        if doc_ids:
            doc_rows = await session.execute(
                select(Document.id, Document.folder_id).where(
                    Document.search_space_id == search_space_id,
                    Document.id.in_(doc_ids),
                )
            )
            folder_by_doc_id = {
                row.id: row.folder_id for row in doc_rows.all() if row.id is not None
            }

    files: dict[str, dict[str, str]] = {}
    for document in documents:
        doc_meta = document.get("document") or {}
        title = str(doc_meta.get("title") or "untitled")
        doc_id = doc_meta.get("id")
        folder_id = folder_by_doc_id.get(doc_id) if isinstance(doc_id, int) else None
        base_folder = folder_paths.get(folder_id, "/documents")
        file_name = _safe_filename(title)
        path = f"{base_folder}/{file_name}"
        matched_ids = set(document.get("matched_chunk_ids") or [])
        xml_content = _build_document_xml(document, matched_chunk_ids=matched_ids)
        files[path] = {
            "content": xml_content.split("\n"),
            "encoding": "utf-8",
            "created_at": "",
            "modified_at": "",
        }
    return files


class KnowledgeBaseSearchMiddleware(AgentMiddleware):  # type: ignore[type-arg]
    """Pre-agent middleware that always searches the KB and seeds a scoped filesystem."""

    tools = ()

    def __init__(
        self,
        *,
        search_space_id: int,
        available_connectors: list[str] | None = None,
        available_document_types: list[str] | None = None,
        top_k: int = 10,
    ) -> None:
        self.search_space_id = search_space_id
        self.available_connectors = available_connectors
        self.available_document_types = available_document_types
        self.top_k = top_k

    def before_agent(  # type: ignore[override]
        self,
        state: AgentState,
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                return None
        except RuntimeError:
            pass
        return asyncio.run(self.abefore_agent(state, runtime))

    async def abefore_agent(  # type: ignore[override]
        self,
        state: AgentState,
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        del runtime
        messages = state.get("messages") or []
        if not messages:
            return None
        last_message = messages[-1]
        if not isinstance(last_message, HumanMessage):
            return None

        user_text = _extract_text_from_message(last_message).strip()
        if not user_text:
            return None

        t0 = _perf_log and asyncio.get_event_loop().time()
        existing_files = state.get("files")

        search_results = await search_knowledge_base(
            query=user_text,
            search_space_id=self.search_space_id,
            available_connectors=self.available_connectors,
            available_document_types=self.available_document_types,
            top_k=self.top_k,
        )
        new_files = await build_scoped_filesystem(
            documents=search_results,
            search_space_id=self.search_space_id,
        )

        ai_msg, tool_msg = _build_synthetic_ls(existing_files, new_files)

        if t0 is not None:
            _perf_log.info(
                "[kb_fs_middleware] completed in %.3fs query=%r new_files=%d total=%d",
                asyncio.get_event_loop().time() - t0,
                user_text[:80],
                len(new_files),
                len(new_files) + len(existing_files or {}),
            )
        return {"files": new_files, "messages": [ai_msg, tool_msg]}
