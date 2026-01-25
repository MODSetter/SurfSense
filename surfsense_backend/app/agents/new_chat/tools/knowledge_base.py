"""
Knowledge base search tool for the SurfSense agent.

This module provides:
- Connector constants and normalization
- Async knowledge base search across multiple connectors
- Document formatting for LLM context
- Tool factory for creating search_knowledge_base tools
"""

import json
from datetime import datetime
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.connector_service import ConnectorService

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
    "TAVILY_API",
    "SEARXNG_API",
    "LINKUP_API",
    "BAIDU_SEARCH_API",
    "LUMA_CONNECTOR",
    "NOTE",
    "BOOKSTACK_CONNECTOR",
    "CRAWLED_URL",
    "CIRCLEBACK",
    "OBSIDIAN_CONNECTOR",
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
    "TAVILY_API": "Tavily web search API results (real-time web search)",
    "SEARXNG_API": "SearxNG search API results (privacy-focused web search)",
    "LINKUP_API": "Linkup search API results (web search)",
    "BAIDU_SEARCH_API": "Baidu search API results (Chinese web search)",
    "LUMA_CONNECTOR": "Luma events and meetings",
    "WEBCRAWLER_CONNECTOR": "Webpages indexed by SurfSense (personally selected websites)",
    "CRAWLED_URL": "Webpages indexed by SurfSense (personally selected websites)",
    "BOOKSTACK_CONNECTOR": "BookStack pages (personal documentation)",
    "CIRCLEBACK": "Circleback meeting notes, transcripts, and action items",
    "OBSIDIAN_CONNECTOR": "Obsidian vault notes and markdown files (personal notes)",
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

    if not connectors_to_search:
        # Search all available connectors if none specified
        return (
            list(available_connectors)
            if available_connectors
            else list(_ALL_CONNECTORS)
        )

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
    return (
        out
        if out
        else (
            list(available_connectors)
            if available_connectors
            else list(_ALL_CONNECTORS)
        )
    )


# =============================================================================
# Document Formatting
# =============================================================================


def format_documents_for_context(documents: list[dict[str, Any]]) -> str:
    """
    Format retrieved documents into a readable context string for the LLM.

    Args:
        documents: List of document dictionaries from connector search

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

    # Render XML expected by citation instructions
    parts: list[str] = []
    for g in grouped.values():
        metadata_json = json.dumps(g["metadata"], ensure_ascii=False)

        parts.append("<document>")
        parts.append("<document_metadata>")
        parts.append(f"  <document_id>{g['document_id']}</document_id>")
        parts.append(f"  <document_type>{g['document_type']}</document_type>")
        parts.append(f"  <title><![CDATA[{g['title']}]]></title>")
        parts.append(f"  <url><![CDATA[{g['url']}]]></url>")
        parts.append(f"  <metadata_json><![CDATA[{metadata_json}]]></metadata_json>")
        parts.append("</document_metadata>")
        parts.append("")
        parts.append("<document_content>")

        for ch in g["chunks"]:
            ch_content = ch["content"]
            ch_id = ch["chunk_id"]
            if ch_id is None:
                parts.append(f"  <chunk><![CDATA[{ch_content}]]></chunk>")
            else:
                parts.append(f"  <chunk id='{ch_id}'><![CDATA[{ch_content}]]></chunk>")

        parts.append("</document_content>")
        parts.append("</document>")
        parts.append("")

    return "\n".join(parts).strip()


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

    Returns:
        Formatted string with search results
    """
    all_documents = []

    # Resolve date range (default last 2 years)
    from app.agents.new_chat.utils import resolve_date_range

    resolved_start_date, resolved_end_date = resolve_date_range(
        start_date=start_date,
        end_date=end_date,
    )

    connectors = _normalize_connectors(connectors_to_search, available_connectors)

    for connector in connectors:
        try:
            if connector == "YOUTUBE_VIDEO":
                _, chunks = await connector_service.search_youtube(
                    user_query=query,
                    search_space_id=search_space_id,
                    top_k=top_k,
                    start_date=resolved_start_date,
                    end_date=resolved_end_date,
                )
                all_documents.extend(chunks)

            elif connector == "EXTENSION":
                _, chunks = await connector_service.search_extension(
                    user_query=query,
                    search_space_id=search_space_id,
                    top_k=top_k,
                    start_date=resolved_start_date,
                    end_date=resolved_end_date,
                )
                all_documents.extend(chunks)

            elif connector == "CRAWLED_URL":
                _, chunks = await connector_service.search_crawled_urls(
                    user_query=query,
                    search_space_id=search_space_id,
                    top_k=top_k,
                    start_date=resolved_start_date,
                    end_date=resolved_end_date,
                )
                all_documents.extend(chunks)

            elif connector == "FILE":
                _, chunks = await connector_service.search_files(
                    user_query=query,
                    search_space_id=search_space_id,
                    top_k=top_k,
                    start_date=resolved_start_date,
                    end_date=resolved_end_date,
                )
                all_documents.extend(chunks)

            elif connector == "SLACK_CONNECTOR":
                _, chunks = await connector_service.search_slack(
                    user_query=query,
                    search_space_id=search_space_id,
                    top_k=top_k,
                    start_date=resolved_start_date,
                    end_date=resolved_end_date,
                )
                all_documents.extend(chunks)

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
    seen_hashes: set[int] = set()
    deduplicated: list[dict[str, Any]] = []
    for doc in all_documents:
        doc_id = (doc.get("document", {}) or {}).get("id")
        content = (doc.get("content", "") or "").strip()
        content_hash = hash(content)

        if (doc_id and doc_id in seen_doc_ids) or content_hash in seen_hashes:
            continue

        if doc_id:
            seen_doc_ids.add(doc_id)
        seen_hashes.add(content_hash)
        deduplicated.append(doc)

    return format_documents_for_context(deduplicated)


def _build_connector_docstring(available_connectors: list[str] | None) -> str:
    """
    Build the connector documentation section for the tool docstring.

    Args:
        available_connectors: List of available connector types, or None for all

    Returns:
        Formatted docstring section listing available connectors
    """
    connectors = available_connectors if available_connectors else list(_ALL_CONNECTORS)

    lines = []
    for connector in connectors:
        # Skip internal names, prefer user-facing aliases
        if connector == "CRAWLED_URL":
            # Show as WEBCRAWLER_CONNECTOR for user-facing docs
            description = CONNECTOR_DESCRIPTIONS.get(connector, connector)
            lines.append(f"- WEBCRAWLER_CONNECTOR: {description}")
        else:
            description = CONNECTOR_DESCRIPTIONS.get(connector, connector)
            lines.append(f"- {connector}: {description}")

    return "\n".join(lines)


# =============================================================================
# Tool Input Schema
# =============================================================================


class SearchKnowledgeBaseInput(BaseModel):
    """Input schema for the search_knowledge_base tool."""

    query: str = Field(
        description="The search query - be specific and include key terms"
    )
    top_k: int = Field(
        default=10,
        description="Number of results to retrieve (default: 10)",
    )
    start_date: str | None = Field(
        default=None,
        description="Optional ISO date/datetime (e.g. '2025-12-12' or '2025-12-12T00:00:00+00:00')",
    )
    end_date: str | None = Field(
        default=None,
        description="Optional ISO date/datetime (e.g. '2025-12-19' or '2025-12-19T23:59:59+00:00')",
    )
    connectors_to_search: list[str] | None = Field(
        default=None,
        description="Optional list of connector enums to search. If omitted, searches all available.",
    )


def create_search_knowledge_base_tool(
    search_space_id: int,
    db_session: AsyncSession,
    connector_service: ConnectorService,
    available_connectors: list[str] | None = None,
    available_document_types: list[str] | None = None,
) -> StructuredTool:
    """
    Factory function to create the search_knowledge_base tool with injected dependencies.

    Args:
        search_space_id: The user's search space ID
        db_session: Database session
        connector_service: Initialized connector service
        available_connectors: Optional list of connector types available in the search space.
                            Used to dynamically generate the tool docstring.
        available_document_types: Optional list of document types that have data in the search space.
                                Used to inform the LLM about what data exists.

    Returns:
        A configured StructuredTool instance
    """
    # Build connector documentation dynamically
    connector_docs = _build_connector_docstring(available_connectors)

    # Build context about available document types
    doc_types_info = ""
    if available_document_types:
        doc_types_info = f"""

## Document types with indexed content in this search space

The following document types have content available for search:
{", ".join(available_document_types)}

Focus searches on these types for best results."""

    # Build the dynamic description for the tool
    # This is what the LLM sees when deciding whether/how to use the tool
    dynamic_description = f"""Search the user's personal knowledge base for relevant information.

Use this tool to find documents, notes, files, web pages, and other content that may help answer the user's question.

IMPORTANT:
- If the user requests a specific source type (e.g. "my notes", "Slack messages"), pass `connectors_to_search=[...]` using the enums below.
- If `connectors_to_search` is omitted/empty, the system will search broadly.
- Only connectors that are enabled/configured for this search space are available.{doc_types_info}

## Available connector enums for `connectors_to_search`

{connector_docs}

NOTE: `WEBCRAWLER_CONNECTOR` is mapped internally to the canonical document type `CRAWLED_URL`."""

    # Capture for closure
    _available_connectors = available_connectors

    async def _search_knowledge_base_impl(
        query: str,
        top_k: int = 10,
        start_date: str | None = None,
        end_date: str | None = None,
        connectors_to_search: list[str] | None = None,
    ) -> str:
        """Implementation function for knowledge base search."""
        from app.agents.new_chat.utils import parse_date_or_datetime

        parsed_start: datetime | None = None
        parsed_end: datetime | None = None

        if start_date:
            parsed_start = parse_date_or_datetime(start_date)
        if end_date:
            parsed_end = parse_date_or_datetime(end_date)

        return await search_knowledge_base_async(
            query=query,
            search_space_id=search_space_id,
            db_session=db_session,
            connector_service=connector_service,
            connectors_to_search=connectors_to_search,
            top_k=top_k,
            start_date=parsed_start,
            end_date=parsed_end,
            available_connectors=_available_connectors,
        )

    # Create StructuredTool with dynamic description
    # This properly sets the description that the LLM sees
    tool = StructuredTool(
        name="search_knowledge_base",
        description=dynamic_description,
        coroutine=_search_knowledge_base_impl,
        args_schema=SearchKnowledgeBaseInput,
    )

    return tool
