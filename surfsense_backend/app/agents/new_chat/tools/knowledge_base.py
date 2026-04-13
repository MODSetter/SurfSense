"""
Knowledge base search tool for the SurfSense agent.

This module provides:
- Connector constants and normalization
- Async knowledge base search across multiple connectors
- Document formatting for LLM context
"""

import asyncio
import contextlib
import json
import re
import time
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import NATIVE_TO_LEGACY_DOCTYPE, shielded_async_session
from app.services.connector_service import ConnectorService
from app.utils.perf import get_perf_logger

# Connectors that call external live-search APIs. These are handled by the
# ``web_search`` tool and must be excluded from knowledge-base searches.
_LIVE_SEARCH_CONNECTORS: set[str] = {
    "TAVILY_API",
    "LINKUP_API",
    "BAIDU_SEARCH_API",
}

# Patterns that indicate the query has no meaningful search signal.
# plainto_tsquery('english', '*') produces an empty tsquery and an embedding
# of '*' is random noise, so both keyword and semantic search degrade to
# arbitrary ordering — large documents (many chunks) dominate by chance.
_DEGENERATE_QUERY_RE = re.compile(
    r"^[\s*?_.#@!\-/\\]+$"  # only wildcards, punctuation, whitespace
)

# Max chunks per document when doing a recency-based browse instead of
# a real search.  We want breadth (many docs) over depth (many chunks).
_BROWSE_MAX_CHUNKS_PER_DOC = 5


def _is_degenerate_query(query: str) -> bool:
    """Return True when the query carries no meaningful search signal.

    Catches wildcard patterns (``*``, ``**``), empty / whitespace-only
    strings, and single-character non-word tokens.  These queries cause
    both keyword search (empty tsquery) and semantic search (meaningless
    embedding) to return effectively random results.
    """
    stripped = query.strip()
    if not stripped:
        return True
    return bool(_DEGENERATE_QUERY_RE.match(stripped))


async def _browse_recent_documents(
    search_space_id: int,
    document_type: str | list[str] | None,
    top_k: int,
    start_date: datetime | None,
    end_date: datetime | None,
) -> list[dict[str, Any]]:
    """Return the most-recent documents (recency-ordered, no search ranking).

    Used as a fallback when the search query is degenerate (e.g. ``*``) and
    semantic / keyword search would produce arbitrary results.  Returns
    document-grouped dicts in the same shape as ``_combined_rrf_search``
    so the rest of the pipeline works unchanged.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    from app.db import Chunk, Document, DocumentType

    perf = get_perf_logger()
    t0 = time.perf_counter()

    base_conditions = [Document.search_space_id == search_space_id]

    if document_type is not None:
        type_list = (
            document_type if isinstance(document_type, list) else [document_type]
        )
        doc_type_enums = []
        for dt in type_list:
            if isinstance(dt, str):
                with contextlib.suppress(KeyError):
                    doc_type_enums.append(DocumentType[dt])
            else:
                doc_type_enums.append(dt)
        if not doc_type_enums:
            return []
        if len(doc_type_enums) == 1:
            base_conditions.append(Document.document_type == doc_type_enums[0])
        else:
            base_conditions.append(Document.document_type.in_(doc_type_enums))

    if start_date is not None:
        base_conditions.append(Document.updated_at >= start_date)
    if end_date is not None:
        base_conditions.append(Document.updated_at <= end_date)

    async with shielded_async_session() as session:
        doc_query = (
            select(Document)
            .options(joinedload(Document.search_space))
            .where(*base_conditions)
            .order_by(Document.updated_at.desc())
            .limit(top_k)
        )
        result = await session.execute(doc_query)
        documents = result.scalars().unique().all()

        if not documents:
            return []

        doc_ids = [d.id for d in documents]

        chunk_query = (
            select(Chunk)
            .where(Chunk.document_id.in_(doc_ids))
            .order_by(Chunk.document_id, Chunk.id)
        )
        chunk_result = await session.execute(chunk_query)
        raw_chunks = chunk_result.scalars().all()

    doc_chunk_counts: dict[int, int] = {}
    doc_chunks: dict[int, list[dict]] = {d.id: [] for d in documents}
    for chunk in raw_chunks:
        did = chunk.document_id
        count = doc_chunk_counts.get(did, 0)
        if count < _BROWSE_MAX_CHUNKS_PER_DOC:
            doc_chunks[did].append({"chunk_id": chunk.id, "content": chunk.content})
            doc_chunk_counts[did] = count + 1

    results: list[dict[str, Any]] = []
    for doc in documents:
        chunks_list = doc_chunks.get(doc.id, [])
        results.append(
            {
                "document_id": doc.id,
                "content": "\n\n".join(
                    c["content"] for c in chunks_list if c.get("content")
                ),
                "score": 0.0,
                "chunks": chunks_list,
                "document": {
                    "id": doc.id,
                    "title": doc.title,
                    "document_type": doc.document_type.value
                    if getattr(doc, "document_type", None)
                    else None,
                    "metadata": doc.document_metadata or {},
                },
                "source": doc.document_type.value
                if getattr(doc, "document_type", None)
                else None,
            }
        )

    perf.info(
        "[kb_browse] recency browse in %.3fs docs=%d space=%d type=%s",
        time.perf_counter() - t0,
        len(results),
        search_space_id,
        document_type,
    )
    return results


# =============================================================================
# Connector Constants and Normalization
# =============================================================================

# Canonical connector values used internally by ConnectorService
# Includes all document types and search source connectors
_ALL_CONNECTORS: list[str] = [
    "EXTENSION",
    "FILE",
    "SLACK_CONNECTOR",
    "TEAMS_CONNECTOR",
    "NOTION_CONNECTOR",
    "YOUTUBE_VIDEO",
    "GITHUB_CONNECTOR",
    "ELASTICSEARCH_CONNECTOR",
    "LINEAR_CONNECTOR",
    "JIRA_CONNECTOR",
    "CONFLUENCE_CONNECTOR",
    "CLICKUP_CONNECTOR",
    "GOOGLE_CALENDAR_CONNECTOR",
    "GOOGLE_GMAIL_CONNECTOR",
    "GOOGLE_DRIVE_FILE",
    "DISCORD_CONNECTOR",
    "AIRTABLE_CONNECTOR",
    "LUMA_CONNECTOR",
    "NOTE",
    "BOOKSTACK_CONNECTOR",
    "CRAWLED_URL",
    "CIRCLEBACK",
    "OBSIDIAN_CONNECTOR",
    "ONEDRIVE_FILE",
    "DROPBOX_FILE",
    "DEXSCREENER_CONNECTOR",
    # Composio connectors
    "COMPOSIO_GOOGLE_DRIVE_CONNECTOR",
    "COMPOSIO_GMAIL_CONNECTOR",
    "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR",
]

# Human-readable descriptions for each connector type
# Used for generating dynamic docstrings and informing the LLM
CONNECTOR_DESCRIPTIONS: dict[str, str] = {
    "EXTENSION": "Web content saved via SurfSense browser extension (personal browsing history)",
    "FILE": "User-uploaded documents (PDFs, Word, etc.) (personal files)",
    "NOTE": "SurfSense Notes (notes created inside SurfSense)",
    "SLACK_CONNECTOR": "Slack conversations and shared content (personal workspace communications)",
    "TEAMS_CONNECTOR": "Microsoft Teams messages and conversations (personal Teams communications)",
    "NOTION_CONNECTOR": "Notion workspace pages and databases (personal knowledge management)",
    "YOUTUBE_VIDEO": "YouTube video transcripts and metadata (personally saved videos)",
    "GITHUB_CONNECTOR": "GitHub repository content and issues (personal repositories and interactions)",
    "ELASTICSEARCH_CONNECTOR": "Elasticsearch indexed documents and data (personal Elasticsearch instances)",
    "LINEAR_CONNECTOR": "Linear project issues and discussions (personal project management)",
    "JIRA_CONNECTOR": "Jira project issues, tickets, and comments (personal project tracking)",
    "CONFLUENCE_CONNECTOR": "Confluence pages and comments (personal project documentation)",
    "CLICKUP_CONNECTOR": "ClickUp tasks and project data (personal task management)",
    "GOOGLE_CALENDAR_CONNECTOR": "Google Calendar events, meetings, and schedules (personal calendar)",
    "GOOGLE_GMAIL_CONNECTOR": "Google Gmail emails and conversations (personal emails)",
    "GOOGLE_DRIVE_FILE": "Google Drive files and documents (personal cloud storage)",
    "DISCORD_CONNECTOR": "Discord server conversations and shared content (personal community)",
    "AIRTABLE_CONNECTOR": "Airtable records, tables, and database content (personal data)",
    "LUMA_CONNECTOR": "Luma events and meetings",
    "WEBCRAWLER_CONNECTOR": "Webpages indexed by SurfSense (personally selected websites)",
    "CRAWLED_URL": "Webpages indexed by SurfSense (personally selected websites)",
    "BOOKSTACK_CONNECTOR": "BookStack pages (personal documentation)",
    "CIRCLEBACK": "Circleback meeting notes, transcripts, and action items",
    "OBSIDIAN_CONNECTOR": "Obsidian vault notes and markdown files (personal notes)",
    "ONEDRIVE_FILE": "Microsoft OneDrive files and documents (personal cloud storage)",
    "DROPBOX_FILE": "Dropbox files and documents (cloud storage)",
    "DEXSCREENER_CONNECTOR": "DexScreener real-time cryptocurrency trading pair data and market information",
    # Composio connectors
    "COMPOSIO_GOOGLE_DRIVE_CONNECTOR": "Google Drive files via Composio (personal cloud storage)",
    "COMPOSIO_GMAIL_CONNECTOR": "Gmail emails via Composio (personal emails)",
    "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR": "Google Calendar events via Composio (personal calendar)",
}


def _normalize_connectors(
    connectors_to_search: list[str] | None,
    available_connectors: list[str] | None = None,
) -> list[str]:
    """
    Normalize connectors provided by the model.

    - Accepts user-facing enums like WEBCRAWLER_CONNECTOR and maps them to canonical
      ConnectorService types.
    - Drops unknown values.
    - If available_connectors is provided, only includes connectors from that list.
    - If connectors_to_search is None/empty, defaults to available_connectors or all.

    Args:
        connectors_to_search: List of connectors requested by the model
        available_connectors: List of connectors actually available in the search space

    Returns:
        List of normalized connector strings to search
    """
    # Determine the set of valid connectors to consider
    valid_set = (
        set(available_connectors) if available_connectors else set(_ALL_CONNECTORS)
    )
    valid_set -= _LIVE_SEARCH_CONNECTORS

    if not connectors_to_search:
        base = (
            list(available_connectors)
            if available_connectors
            else list(_ALL_CONNECTORS)
        )
        return [c for c in base if c not in _LIVE_SEARCH_CONNECTORS]

    normalized: list[str] = []
    for raw in connectors_to_search:
        c = (raw or "").strip().upper()
        if not c:
            continue
        # Map user-facing aliases to canonical names
        if c == "WEBCRAWLER_CONNECTOR":
            c = "CRAWLED_URL"
        normalized.append(c)

    # de-dupe while preserving order + filter to valid connectors
    seen: set[str] = set()
    out: list[str] = []
    for c in normalized:
        if c in seen:
            continue
        # Only include if it's a known connector AND available
        if c not in _ALL_CONNECTORS:
            continue
        if c not in valid_set:
            continue
        seen.add(c)
        out.append(c)

    # Fallback to all available if nothing matched
    if not out:
        base = (
            list(available_connectors)
            if available_connectors
            else list(_ALL_CONNECTORS)
        )
        return [c for c in base if c not in _LIVE_SEARCH_CONNECTORS]
    return out


# =============================================================================
# Document Formatting
# =============================================================================


# Fraction of the model's context window (in characters) that a single tool
# result is allowed to occupy.  The remainder is reserved for system prompt,
# conversation history, and model output.  With ~4 chars/token this gives a
# tool result ≈ 25 % of the context budget in tokens.
_TOOL_OUTPUT_CONTEXT_FRACTION = 0.25
_CHARS_PER_TOKEN = 4

# Hard-floor / ceiling so the budget is always sensible regardless of what
# the model reports.
_MIN_TOOL_OUTPUT_CHARS = 20_000  # ~5K tokens
_MAX_TOOL_OUTPUT_CHARS = 200_000  # ~50K tokens
_MAX_CHUNK_CHARS = 8_000

# Rank-adaptive per-document budget allocation.
# Top-ranked (most relevant) documents get a larger share of the budget so
# we pack as much high-quality context as possible.
#
#   fraction(rank) = _TOP_DOC_BUDGET_FRACTION / (1 + rank * _RANK_DECAY)
#
# Examples (128K budget, 8K chunk cap):
#   rank 0 → 40% → 6 chunks   |  rank 3 → 19% → 3 chunks
#   rank 1 → 30% → 4 chunks   |  rank 10 → 10% → 3 chunks (floor)
#   rank 2 → 24% → 3 chunks   |
_TOP_DOC_BUDGET_FRACTION = 0.40
_RANK_DECAY = 0.35
_MIN_CHUNKS_PER_DOC = 3


def _compute_tool_output_budget(max_input_tokens: int | None) -> int:
    """Derive a character budget from the model's context window.

    Uses ``litellm.get_model_info`` via the value already resolved by
    ``ChatLiteLLMRouter`` / ``ChatLiteLLM`` and passed through the dependency
    chain as ``max_input_tokens``.  Falls back to a conservative default when
    the value is unavailable.
    """
    if max_input_tokens is None or max_input_tokens <= 0:
        return _MIN_TOOL_OUTPUT_CHARS  # conservative fallback

    budget = int(max_input_tokens * _CHARS_PER_TOKEN * _TOOL_OUTPUT_CONTEXT_FRACTION)
    return max(_MIN_TOOL_OUTPUT_CHARS, min(budget, _MAX_TOOL_OUTPUT_CHARS))


_INTERNAL_METADATA_KEYS: frozenset[str] = frozenset(
    {
        "message_id",
        "thread_id",
        "event_id",
        "calendar_id",
        "google_drive_file_id",
        "onedrive_file_id",
        "dropbox_file_id",
        "page_id",
        "issue_id",
        "connector_id",
    }
)


def format_documents_for_context(
    documents: list[dict[str, Any]],
    *,
    max_chars: int = _MAX_TOOL_OUTPUT_CHARS,
    max_chunk_chars: int = _MAX_CHUNK_CHARS,
    max_chunks_per_doc: int = 0,
) -> str:
    """
    Format retrieved documents into a readable context string for the LLM.

    Documents are added in order (highest relevance first) until the character
    budget is reached.  Individual chunks are capped at ``max_chunk_chars`` and
    each document is limited to a dynamically computed chunk cap so a single
    large document cannot monopolize the output while still maximising the use
    of available context space.

    Args:
        documents: List of document dictionaries from connector search
        max_chars: Approximate character budget for the entire output.
        max_chunk_chars: Per-chunk character cap (content is tail-truncated).
        max_chunks_per_doc: Maximum chunks per document.  ``0`` (default) means
            auto-compute per document using a rank-adaptive formula so
            higher-ranked documents receive more chunks.

    Returns:
        Formatted string with document contents and metadata
    """
    if not documents:
        return ""

    # Group chunks by document id (preferred) to produce the XML structure.
    #
    # IMPORTANT: ConnectorService returns **document-grouped** results of the form:
    #   {
    #     "document": {...},
    #     "chunks": [{"chunk_id": 123, "content": "..."}, ...],
    #     "source": "NOTION_CONNECTOR" | "FILE" | ...
    #   }
    #
    # We must preserve chunk_id so citations like [citation:123] are possible.
    grouped: dict[str, dict[str, Any]] = {}

    for doc in documents:
        document_info = (doc.get("document") or {}) if isinstance(doc, dict) else {}
        metadata = (
            (document_info.get("metadata") or {})
            if isinstance(document_info, dict)
            else {}
        )
        if not metadata and isinstance(doc, dict):
            # Some result shapes may place metadata at the top level.
            metadata = doc.get("metadata") or {}

        source = (
            (doc.get("source") if isinstance(doc, dict) else None)
            or document_info.get("document_type")
            or metadata.get("document_type")
            or "UNKNOWN"
        )

        # Document identity (prefer document_id; otherwise fall back to type+title+url)
        document_id_val = document_info.get("id")
        title = (
            document_info.get("title") or metadata.get("title") or "Untitled Document"
        )
        url = (
            metadata.get("url")
            or metadata.get("source")
            or metadata.get("page_url")
            or ""
        )

        doc_key = (
            str(document_id_val)
            if document_id_val is not None
            else f"{source}::{title}::{url}"
        )

        if doc_key not in grouped:
            grouped[doc_key] = {
                "document_id": document_id_val
                if document_id_val is not None
                else doc_key,
                "document_type": metadata.get("document_type") or source,
                "title": title,
                "url": url,
                "metadata": metadata,
                "chunks": [],
            }

        # Prefer document-grouped chunks if available
        chunks_list = doc.get("chunks") if isinstance(doc, dict) else None
        if isinstance(chunks_list, list) and chunks_list:
            for ch in chunks_list:
                if not isinstance(ch, dict):
                    continue
                chunk_id = ch.get("chunk_id") or ch.get("id")
                content = (ch.get("content") or "").strip()
                if not content:
                    continue
                grouped[doc_key]["chunks"].append(
                    {"chunk_id": chunk_id, "content": content}
                )
            continue

        # Fallback: treat this as a flat chunk-like object
        if not isinstance(doc, dict):
            continue
        chunk_id = doc.get("chunk_id") or doc.get("id")
        content = (doc.get("content") or "").strip()
        if not content:
            continue
        grouped[doc_key]["chunks"].append({"chunk_id": chunk_id, "content": content})

    # Live search connectors whose results should be cited by URL rather than
    # a numeric chunk_id (the numeric IDs are meaningless auto-incremented counters).
    live_search_connectors = {
        "TAVILY_API",
        "LINKUP_API",
        "BAIDU_SEARCH_API",
    }

    # Render XML expected by citation instructions, respecting the char budget.
    parts: list[str] = []
    total_chars = 0
    total_docs = len(grouped)

    for doc_idx, g in enumerate(grouped.values()):
        metadata_clean = {
            k: v for k, v in g["metadata"].items() if k not in _INTERNAL_METADATA_KEYS
        }
        metadata_json = json.dumps(metadata_clean, ensure_ascii=False)
        is_live_search = g["document_type"] in live_search_connectors

        doc_lines: list[str] = [
            "<document>",
            "<document_metadata>",
            f"  <document_id>{g['document_id']}</document_id>",
            f"  <document_type>{g['document_type']}</document_type>",
            f"  <title><![CDATA[{g['title']}]]></title>",
            f"  <url><![CDATA[{g['url']}]]></url>",
            f"  <metadata_json><![CDATA[{metadata_json}]]></metadata_json>",
            "</document_metadata>",
            "",
            "<document_content>",
        ]

        # Rank-adaptive per-document chunk cap: top results get more chunks.
        if max_chunks_per_doc > 0:
            chunks_allowed = max_chunks_per_doc
        else:
            doc_fraction = _TOP_DOC_BUDGET_FRACTION / (1 + doc_idx * _RANK_DECAY)
            max_doc_chars = int(max_chars * doc_fraction)
            xml_overhead = 500
            chunks_allowed = max(
                (max_doc_chars - xml_overhead) // max(max_chunk_chars, 1),
                _MIN_CHUNKS_PER_DOC,
            )

        chunks = g["chunks"]
        if len(chunks) > chunks_allowed:
            chunks = chunks[:chunks_allowed]

        for ch in chunks:
            ch_content = ch["content"]
            if max_chunk_chars and len(ch_content) > max_chunk_chars:
                ch_content = ch_content[:max_chunk_chars] + "\n...(truncated)"
            ch_id = g["url"] if (is_live_search and g["url"]) else ch["chunk_id"]
            if ch_id is None:
                doc_lines.append(f"  <chunk><![CDATA[{ch_content}]]></chunk>")
            else:
                doc_lines.append(
                    f"  <chunk id='{ch_id}'><![CDATA[{ch_content}]]></chunk>"
                )

        doc_lines.extend(["</document_content>", "</document>", ""])

        doc_xml = "\n".join(doc_lines)
        doc_len = len(doc_xml)

        if total_chars + doc_len > max_chars:
            remaining = total_docs - doc_idx
            if doc_idx == 0:
                parts.append(doc_xml)
                total_chars += doc_len
            parts.append(
                f"<!-- Output truncated: {remaining} more document(s) omitted "
                f"(budget {max_chars} chars). Refine your query or reduce top_k "
                f"to retrieve different results. -->"
            )
            break

        parts.append(doc_xml)
        total_chars += doc_len

    result = "\n".join(parts).strip()

    # Hard safety net: if the result is still over budget (e.g. a single massive
    # first document), forcibly truncate with a closing comment.
    if len(result) > max_chars:
        truncation_msg = "\n<!-- ...output forcibly truncated to fit context window -->"
        result = result[: max_chars - len(truncation_msg)] + truncation_msg

    return result


# =============================================================================
# Knowledge Base Search
# =============================================================================


async def search_knowledge_base_async(
    query: str,
    search_space_id: int,
    db_session: AsyncSession,
    connector_service: ConnectorService,
    connectors_to_search: list[str] | None = None,
    top_k: int = 10,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    available_connectors: list[str] | None = None,
    available_document_types: list[str] | None = None,
    max_input_tokens: int | None = None,
) -> str:
    """
    Search the user's knowledge base for relevant documents.

    This is the async implementation that searches across multiple connectors.

    Args:
        query: The search query
        search_space_id: The user's search space ID
        db_session: Database session
        connector_service: Initialized connector service
        connectors_to_search: Optional list of connector types to search. If omitted, searches all.
        top_k: Number of results per connector
        start_date: Optional start datetime (UTC) for filtering documents
        end_date: Optional end datetime (UTC) for filtering documents
        available_connectors: Optional list of connectors actually available in the search space.
                            If provided, only these connectors will be searched.
        available_document_types: Optional list of document types that actually have indexed
                                data. When provided, local connectors whose document type is
                                absent are skipped entirely (no embedding / DB round-trip).
        max_input_tokens: Model context window size (tokens).  Used to dynamically
                         size the output so it fits within the model's limits.

    Returns:
        Formatted string with search results
    """
    perf = get_perf_logger()
    t0 = time.perf_counter()

    deduplicated = await search_knowledge_base_raw_async(
        query=query,
        search_space_id=search_space_id,
        db_session=db_session,
        connector_service=connector_service,
        connectors_to_search=connectors_to_search,
        top_k=top_k,
        start_date=start_date,
        end_date=end_date,
        available_connectors=available_connectors,
        available_document_types=available_document_types,
    )

    if not deduplicated:
        return "No documents found in the knowledge base. The search space has no indexed content yet."

    # Use browse chunk cap for degenerate queries, otherwise adaptive chunking.
    max_chunks_per_doc = (
        _BROWSE_MAX_CHUNKS_PER_DOC if _is_degenerate_query(query) else 0
    )
    output_budget = _compute_tool_output_budget(max_input_tokens)
    result = format_documents_for_context(
        deduplicated,
        max_chars=output_budget,
        max_chunks_per_doc=max_chunks_per_doc,
    )

    if len(result) > output_budget:
        perf.warning(
            "[kb_search] output STILL exceeds budget after format (%d > %d), "
            "hard truncation should have fired",
            len(result),
            output_budget,
        )

    perf.info(
        "[kb_search] TOTAL in %.3fs total_docs=%d deduped=%d output_chars=%d "
        "budget=%d max_input_tokens=%s space=%d",
        time.perf_counter() - t0,
        len(deduplicated),
        len(deduplicated),
        len(result),
        output_budget,
        max_input_tokens,
        search_space_id,
    )
    return result


async def search_knowledge_base_raw_async(
    query: str,
    search_space_id: int,
    db_session: AsyncSession,
    connector_service: ConnectorService,
    connectors_to_search: list[str] | None = None,
    top_k: int = 10,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    available_connectors: list[str] | None = None,
    available_document_types: list[str] | None = None,
    query_embedding: list[float] | None = None,
) -> list[dict[str, Any]]:
    """Search knowledge base and return raw document dicts (no XML formatting)."""
    perf = get_perf_logger()
    t0 = time.perf_counter()
    all_documents: list[dict[str, Any]] = []

    # Preserve the public signature for compatibility even if values are unused.
    _ = (db_session, connector_service)

    from app.agents.new_chat.utils import resolve_date_range

    resolved_start_date, resolved_end_date = resolve_date_range(
        start_date=start_date,
        end_date=end_date,
    )

    connectors = _normalize_connectors(connectors_to_search, available_connectors)

    if available_document_types:
        doc_types_set = set(available_document_types)
        connectors = [
            c
            for c in connectors
            if c in doc_types_set
            or NATIVE_TO_LEGACY_DOCTYPE.get(c, "") in doc_types_set
        ]

    if not connectors:
        return []

    if _is_degenerate_query(query):
        perf.info(
            "[kb_search_raw] degenerate query %r detected - recency browse",
            query,
        )
        browse_connectors = connectors if connectors else [None]  # type: ignore[list-item]
        expanded_browse = []
        for connector in browse_connectors:
            if connector is not None and connector in NATIVE_TO_LEGACY_DOCTYPE:
                expanded_browse.append([connector, NATIVE_TO_LEGACY_DOCTYPE[connector]])
            else:
                expanded_browse.append(connector)
        browse_results = await asyncio.gather(
            *[
                _browse_recent_documents(
                    search_space_id=search_space_id,
                    document_type=connector,
                    top_k=top_k,
                    start_date=resolved_start_date,
                    end_date=resolved_end_date,
                )
                for connector in expanded_browse
            ]
        )
        for docs in browse_results:
            all_documents.extend(docs)
    else:
        if query_embedding is None:
            from app.config import config as app_config

            query_embedding = app_config.embedding_model_instance.embed(query)

        max_parallel_searches = 4
        semaphore = asyncio.Semaphore(max_parallel_searches)

        async def _search_one_connector(connector: str) -> list[dict[str, Any]]:
            try:
                async with semaphore, shielded_async_session() as isolated_session:
                    svc = ConnectorService(isolated_session, search_space_id)
                    return await svc._combined_rrf_search(
                        query_text=query,
                        search_space_id=search_space_id,
                        document_type=connector,
                        top_k=top_k,
                        start_date=resolved_start_date,
                        end_date=resolved_end_date,
                        query_embedding=query_embedding,
                    )
            except Exception as exc:
                perf.warning("[kb_search_raw] connector=%s FAILED: %s", connector, exc)
                return []

        connector_results = await asyncio.gather(
            *[_search_one_connector(connector) for connector in connectors]
        )
        for docs in connector_results:
            all_documents.extend(docs)

            elif connector == "TEAMS_CONNECTOR":
                _, chunks = await connector_service.search_teams(
                    user_query=query,
                    search_space_id=search_space_id,
                    top_k=top_k,
                    start_date=resolved_start_date,
                    end_date=resolved_end_date,
                )
                all_documents.extend(chunks)

            elif connector == "NOTION_CONNECTOR":
                _, chunks = await connector_service.search_notion(
                    user_query=query,
                    search_space_id=search_space_id,
                    top_k=top_k,
                    start_date=resolved_start_date,
                    end_date=resolved_end_date,
                )
                all_documents.extend(chunks)

            elif connector == "GITHUB_CONNECTOR":
                _, chunks = await connector_service.search_github(
                    user_query=query,
                    search_space_id=search_space_id,
                    top_k=top_k,
                    start_date=resolved_start_date,
                    end_date=resolved_end_date,
                )
                all_documents.extend(chunks)

            elif connector == "LINEAR_CONNECTOR":
                _, chunks = await connector_service.search_linear(
                    user_query=query,
                    search_space_id=search_space_id,
                    top_k=top_k,
                    start_date=resolved_start_date,
                    end_date=resolved_end_date,
                )
                all_documents.extend(chunks)

            elif connector == "TAVILY_API":
                _, chunks = await connector_service.search_tavily(
                    user_query=query,
                    search_space_id=search_space_id,
                    top_k=top_k,
                )
                all_documents.extend(chunks)

            elif connector == "SEARXNG_API":
                _, chunks = await connector_service.search_searxng(
                    user_query=query,
                    search_space_id=search_space_id,
                    top_k=top_k,
                )
                all_documents.extend(chunks)

            elif connector == "LINKUP_API":
                # Keep behavior aligned with researcher: default "standard"
                _, chunks = await connector_service.search_linkup(
                    user_query=query,
                    search_space_id=search_space_id,
                    mode="standard",
                )
                all_documents.extend(chunks)

            elif connector == "BAIDU_SEARCH_API":
                _, chunks = await connector_service.search_baidu(
                    user_query=query,
                    search_space_id=search_space_id,
                    top_k=top_k,
                )
                all_documents.extend(chunks)

            elif connector == "DISCORD_CONNECTOR":
                _, chunks = await connector_service.search_discord(
                    user_query=query,
                    search_space_id=search_space_id,
                    top_k=top_k,
                    start_date=resolved_start_date,
                    end_date=resolved_end_date,
                )
                all_documents.extend(chunks)

            elif connector == "JIRA_CONNECTOR":
                _, chunks = await connector_service.search_jira(
                    user_query=query,
                    search_space_id=search_space_id,
                    top_k=top_k,
                    start_date=resolved_start_date,
                    end_date=resolved_end_date,
                )
                all_documents.extend(chunks)

            elif connector == "GOOGLE_CALENDAR_CONNECTOR":
                _, chunks = await connector_service.search_google_calendar(
                    user_query=query,
                    search_space_id=search_space_id,
                    top_k=top_k,
                    start_date=resolved_start_date,
                    end_date=resolved_end_date,
                )
                all_documents.extend(chunks)

            elif connector == "AIRTABLE_CONNECTOR":
                _, chunks = await connector_service.search_airtable(
                    user_query=query,
                    search_space_id=search_space_id,
                    top_k=top_k,
                    start_date=resolved_start_date,
                    end_date=resolved_end_date,
                )
                all_documents.extend(chunks)

            elif connector == "GOOGLE_GMAIL_CONNECTOR":
                _, chunks = await connector_service.search_google_gmail(
                    user_query=query,
                    search_space_id=search_space_id,
                    top_k=top_k,
                    start_date=resolved_start_date,
                    end_date=resolved_end_date,
                )
                all_documents.extend(chunks)

            elif connector == "GOOGLE_DRIVE_FILE":
                _, chunks = await connector_service.search_google_drive(
                    user_query=query,
                    search_space_id=search_space_id,
                    top_k=top_k,
                    start_date=resolved_start_date,
                    end_date=resolved_end_date,
                )
                all_documents.extend(chunks)

            elif connector == "CONFLUENCE_CONNECTOR":
                _, chunks = await connector_service.search_confluence(
                    user_query=query,
                    search_space_id=search_space_id,
                    top_k=top_k,
                    start_date=resolved_start_date,
                    end_date=resolved_end_date,
                )
                all_documents.extend(chunks)

            elif connector == "CLICKUP_CONNECTOR":
                _, chunks = await connector_service.search_clickup(
                    user_query=query,
                    search_space_id=search_space_id,
                    top_k=top_k,
                    start_date=resolved_start_date,
                    end_date=resolved_end_date,
                )
                all_documents.extend(chunks)

            elif connector == "LUMA_CONNECTOR":
                _, chunks = await connector_service.search_luma(
                    user_query=query,
                    search_space_id=search_space_id,
                    top_k=top_k,
                    start_date=resolved_start_date,
                    end_date=resolved_end_date,
                )
                all_documents.extend(chunks)

            elif connector == "ELASTICSEARCH_CONNECTOR":
                _, chunks = await connector_service.search_elasticsearch(
                    user_query=query,
                    search_space_id=search_space_id,
                    top_k=top_k,
                    start_date=resolved_start_date,
                    end_date=resolved_end_date,
                )
                all_documents.extend(chunks)

            elif connector == "NOTE":
                _, chunks = await connector_service.search_notes(
                    user_query=query,
                    search_space_id=search_space_id,
                    top_k=top_k,
                    start_date=resolved_start_date,
                    end_date=resolved_end_date,
                )
                all_documents.extend(chunks)

            elif connector == "BOOKSTACK_CONNECTOR":
                _, chunks = await connector_service.search_bookstack(
                    user_query=query,
                    search_space_id=search_space_id,
                    top_k=top_k,
                    start_date=resolved_start_date,
                    end_date=resolved_end_date,
                )
                all_documents.extend(chunks)

            elif connector == "CIRCLEBACK":
                _, chunks = await connector_service.search_circleback(
                    user_query=query,
                    search_space_id=search_space_id,
                    top_k=top_k,
                    start_date=resolved_start_date,
                    end_date=resolved_end_date,
                )
                all_documents.extend(chunks)

            elif connector == "OBSIDIAN_CONNECTOR":
                _, chunks = await connector_service.search_obsidian(
                    user_query=query,
                    search_space_id=search_space_id,
                    top_k=top_k,
                    start_date=resolved_start_date,
                    end_date=resolved_end_date,
                )
                all_documents.extend(chunks)

            elif connector == "DEXSCREENER_CONNECTOR":
                _, chunks = await connector_service.search_dexscreener(
                    user_query=query,
                    search_space_id=search_space_id,
                    top_k=top_k,
                    start_date=resolved_start_date,
                    end_date=resolved_end_date,
                )
                print(f"[DEBUG] DexScreener search returned {len(chunks)} chunks")
                if chunks:
                    print(f"[DEBUG] First chunk metadata: {chunks[0].get('document', {}).get('metadata', {})}")
                all_documents.extend(chunks)

            # =========================================================
            # Composio Connectors
            # =========================================================
            elif connector == "COMPOSIO_GOOGLE_DRIVE_CONNECTOR":
                _, chunks = await connector_service.search_composio_google_drive(
                    user_query=query,
                    search_space_id=search_space_id,
                    top_k=top_k,
                    start_date=resolved_start_date,
                    end_date=resolved_end_date,
                )
                all_documents.extend(chunks)

            elif connector == "COMPOSIO_GMAIL_CONNECTOR":
                _, chunks = await connector_service.search_composio_gmail(
                    user_query=query,
                    search_space_id=search_space_id,
                    top_k=top_k,
                    start_date=resolved_start_date,
                    end_date=resolved_end_date,
                )
                all_documents.extend(chunks)

            elif connector == "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR":
                _, chunks = await connector_service.search_composio_google_calendar(
                    user_query=query,
                    search_space_id=search_space_id,
                    top_k=top_k,
                    start_date=resolved_start_date,
                    end_date=resolved_end_date,
                )
                all_documents.extend(chunks)

        except Exception as e:
            print(f"Error searching connector {connector}: {e}")
            continue

    # Deduplicate by content hash
    seen_doc_ids: set[Any] = set()
    seen_content_hashes: set[int] = set()
    deduplicated: list[dict[str, Any]] = []

    def _content_fingerprint(document: dict[str, Any]) -> int | None:
        chunks = document.get("chunks")
        if isinstance(chunks, list):
            chunk_texts = []
            for chunk in chunks:
                if not isinstance(chunk, dict):
                    continue
                chunk_content = (chunk.get("content") or "").strip()
                if chunk_content:
                    chunk_texts.append(chunk_content)
            if chunk_texts:
                return hash("||".join(chunk_texts))
        flat_content = (document.get("content") or "").strip()
        if flat_content:
            return hash(flat_content)
        return None

    for doc in all_documents:
        doc_id = (doc.get("document", {}) or {}).get("id")
        if doc_id is not None:
            if doc_id in seen_doc_ids:
                continue
            seen_doc_ids.add(doc_id)
            deduplicated.append(doc)
            continue
        content_hash = _content_fingerprint(doc)
        if content_hash is not None and content_hash in seen_content_hashes:
            continue
        if content_hash is not None:
            seen_content_hashes.add(content_hash)
        deduplicated.append(doc)

    deduplicated.sort(key=lambda doc: doc.get("score", 0), reverse=True)
    perf.info(
        "[kb_search_raw] done in %.3fs total=%d deduped=%d",
        time.perf_counter() - t0,
        len(all_documents),
        len(deduplicated),
    )
    return deduplicated
