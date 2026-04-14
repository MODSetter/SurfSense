"""AI File Sort Service: builds connector-type/date/category/subcategory folder paths."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime

from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db import (
    Chunk,
    Document,
    DocumentType,
    SearchSourceConnector,
    SearchSourceConnectorType,
)
from app.services.folder_service import ensure_folder_hierarchy_with_depth_validation

logger = logging.getLogger(__name__)

_DOCTYPE_TO_CONNECTOR_LABEL: dict[str, str] = {
    DocumentType.EXTENSION: "Browser Extension",
    DocumentType.CRAWLED_URL: "Web Crawl",
    DocumentType.FILE: "File Upload",
    DocumentType.SLACK_CONNECTOR: "Slack",
    DocumentType.TEAMS_CONNECTOR: "Teams",
    DocumentType.ONEDRIVE_FILE: "OneDrive",
    DocumentType.NOTION_CONNECTOR: "Notion",
    DocumentType.YOUTUBE_VIDEO: "YouTube",
    DocumentType.GITHUB_CONNECTOR: "GitHub",
    DocumentType.LINEAR_CONNECTOR: "Linear",
    DocumentType.DISCORD_CONNECTOR: "Discord",
    DocumentType.JIRA_CONNECTOR: "Jira",
    DocumentType.CONFLUENCE_CONNECTOR: "Confluence",
    DocumentType.CLICKUP_CONNECTOR: "ClickUp",
    DocumentType.GOOGLE_CALENDAR_CONNECTOR: "Google Calendar",
    DocumentType.GOOGLE_GMAIL_CONNECTOR: "Gmail",
    DocumentType.GOOGLE_DRIVE_FILE: "Google Drive",
    DocumentType.AIRTABLE_CONNECTOR: "Airtable",
    DocumentType.LUMA_CONNECTOR: "Luma",
    DocumentType.ELASTICSEARCH_CONNECTOR: "Elasticsearch",
    DocumentType.BOOKSTACK_CONNECTOR: "BookStack",
    DocumentType.CIRCLEBACK: "Circleback",
    DocumentType.OBSIDIAN_CONNECTOR: "Obsidian",
    DocumentType.NOTE: "Notes",
    DocumentType.DROPBOX_FILE: "Dropbox",
    DocumentType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR: "Google Drive (Composio)",
    DocumentType.COMPOSIO_GMAIL_CONNECTOR: "Gmail (Composio)",
    DocumentType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR: "Google Calendar (Composio)",
    DocumentType.LOCAL_FOLDER_FILE: "Local Folder",
}

_CONNECTOR_TYPE_LABEL: dict[str, str] = {
    SearchSourceConnectorType.SERPER_API: "Serper Search",
    SearchSourceConnectorType.TAVILY_API: "Tavily Search",
    SearchSourceConnectorType.SEARXNG_API: "SearXNG Search",
    SearchSourceConnectorType.LINKUP_API: "Linkup Search",
    SearchSourceConnectorType.BAIDU_SEARCH_API: "Baidu Search",
    SearchSourceConnectorType.SLACK_CONNECTOR: "Slack",
    SearchSourceConnectorType.TEAMS_CONNECTOR: "Teams",
    SearchSourceConnectorType.ONEDRIVE_CONNECTOR: "OneDrive",
    SearchSourceConnectorType.NOTION_CONNECTOR: "Notion",
    SearchSourceConnectorType.GITHUB_CONNECTOR: "GitHub",
    SearchSourceConnectorType.LINEAR_CONNECTOR: "Linear",
    SearchSourceConnectorType.DISCORD_CONNECTOR: "Discord",
    SearchSourceConnectorType.JIRA_CONNECTOR: "Jira",
    SearchSourceConnectorType.CONFLUENCE_CONNECTOR: "Confluence",
    SearchSourceConnectorType.CLICKUP_CONNECTOR: "ClickUp",
    SearchSourceConnectorType.GOOGLE_CALENDAR_CONNECTOR: "Google Calendar",
    SearchSourceConnectorType.GOOGLE_GMAIL_CONNECTOR: "Gmail",
    SearchSourceConnectorType.GOOGLE_DRIVE_CONNECTOR: "Google Drive",
    SearchSourceConnectorType.AIRTABLE_CONNECTOR: "Airtable",
    SearchSourceConnectorType.LUMA_CONNECTOR: "Luma",
    SearchSourceConnectorType.ELASTICSEARCH_CONNECTOR: "Elasticsearch",
    SearchSourceConnectorType.WEBCRAWLER_CONNECTOR: "Web Crawl",
    SearchSourceConnectorType.BOOKSTACK_CONNECTOR: "BookStack",
    SearchSourceConnectorType.CIRCLEBACK_CONNECTOR: "Circleback",
    SearchSourceConnectorType.OBSIDIAN_CONNECTOR: "Obsidian",
    SearchSourceConnectorType.MCP_CONNECTOR: "MCP",
    SearchSourceConnectorType.DROPBOX_CONNECTOR: "Dropbox",
    SearchSourceConnectorType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR: "Google Drive (Composio)",
    SearchSourceConnectorType.COMPOSIO_GMAIL_CONNECTOR: "Gmail (Composio)",
    SearchSourceConnectorType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR: "Google Calendar (Composio)",
}

_MAX_CONTENT_CHARS = 4000
_MAX_CHUNKS_FOR_CONTEXT = 5

_CATEGORY_PROMPT = (
    "Based on the document information below, classify it into a broad category "
    "and a more specific subcategory.\n\n"
    "Rules:\n"
    "- category: 1-2 word broad theme (e.g. Science, Finance, Engineering, Communication, Media)\n"
    "- subcategory: 1-2 word specific topic within the category "
    "(e.g. Physics, Tax Reports, Backend, Team Updates)\n"
    "- Use nouns only. Do not include generic terms like 'General' or 'Miscellaneous'.\n\n"
    "Title: {title}\n\n"
    "Content: {summary}\n\n"
    'Respond with ONLY a JSON object: {{"category": "...", "subcategory": "..."}}'
)

_SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9 _\-()]")
_FALLBACK_CATEGORY = "Uncategorized"
_FALLBACK_SUBCATEGORY = "General"


def resolve_root_folder_label(
    document: Document, connector: SearchSourceConnector | None
) -> str:
    if connector is not None:
        return _CONNECTOR_TYPE_LABEL.get(
            connector.connector_type, str(connector.connector_type)
        )
    return _DOCTYPE_TO_CONNECTOR_LABEL.get(
        document.document_type, str(document.document_type)
    )


def resolve_date_folder(document: Document) -> str:
    ts = document.updated_at or document.created_at
    if ts is None:
        ts = datetime.now(UTC)
    return ts.strftime("%Y-%m-%d")


def sanitize_category_folder_name(
    value: str | None, fallback: str = _FALLBACK_CATEGORY
) -> str:
    if not value or not value.strip():
        return fallback
    cleaned = _SAFE_NAME_RE.sub("", value.strip())
    cleaned = " ".join(cleaned.split())
    if not cleaned:
        return fallback
    return cleaned[:50]


async def _resolve_document_text(
    session: AsyncSession,
    document: Document,
) -> str:
    """Build the best available text representation for taxonomy generation.

    Prefers ``document.content``; falls back to joining the first few chunks
    when content is empty or too short to be useful.
    """
    text = (document.content or "").strip()
    if len(text) >= 100:
        return text[:_MAX_CONTENT_CHARS]

    stmt = (
        select(Chunk.content)
        .where(Chunk.document_id == document.id)
        .order_by(Chunk.id)
        .limit(_MAX_CHUNKS_FOR_CONTEXT)
    )
    result = await session.execute(stmt)
    chunk_texts = [row[0] for row in result.all() if row[0]]
    if chunk_texts:
        combined = "\n\n".join(chunk_texts)
        return combined[:_MAX_CONTENT_CHARS]

    return text[:_MAX_CONTENT_CHARS]


def _get_cached_taxonomy(document: Document) -> tuple[str, str] | None:
    """Return (category, subcategory) from document metadata cache, or None."""
    meta = document.document_metadata
    if not isinstance(meta, dict):
        return None
    cat = meta.get("ai_sort_category")
    subcat = meta.get("ai_sort_subcategory")
    if cat and subcat and isinstance(cat, str) and isinstance(subcat, str):
        return cat, subcat
    return None


def _set_cached_taxonomy(document: Document, category: str, subcategory: str) -> None:
    """Persist the AI taxonomy on document metadata for deterministic re-sorts."""
    meta = dict(document.document_metadata or {})
    meta["ai_sort_category"] = category
    meta["ai_sort_subcategory"] = subcategory
    document.document_metadata = meta


async def generate_ai_taxonomy(
    title: str,
    summary_or_content: str,
    llm,
) -> tuple[str, str]:
    """Return (category, subcategory) using a single structured LLM call."""
    text = (summary_or_content or "").strip()
    if not text:
        return _FALLBACK_CATEGORY, _FALLBACK_SUBCATEGORY

    if len(text) > _MAX_CONTENT_CHARS:
        text = text[:_MAX_CONTENT_CHARS]

    prompt = _CATEGORY_PROMPT.format(title=title or "Untitled", summary=text)
    try:
        result = await llm.ainvoke([HumanMessage(content=prompt)])
        raw = result.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        parsed = json.loads(raw)
        category = sanitize_category_folder_name(
            parsed.get("category"), _FALLBACK_CATEGORY
        )
        subcategory = sanitize_category_folder_name(
            parsed.get("subcategory"), _FALLBACK_SUBCATEGORY
        )
        return category, subcategory
    except Exception:
        logger.warning("AI taxonomy generation failed, using fallback", exc_info=True)
        return _FALLBACK_CATEGORY, _FALLBACK_SUBCATEGORY


def _build_path_segments(
    root_label: str,
    date_label: str,
    category: str,
    subcategory: str,
) -> list[dict]:
    return [
        {"name": root_label, "metadata": {"ai_sort": True, "ai_sort_level": 1}},
        {"name": date_label, "metadata": {"ai_sort": True, "ai_sort_level": 2}},
        {"name": category, "metadata": {"ai_sort": True, "ai_sort_level": 3}},
        {"name": subcategory, "metadata": {"ai_sort": True, "ai_sort_level": 4}},
    ]


async def _resolve_taxonomy(
    session: AsyncSession,
    document: Document,
    llm,
) -> tuple[str, str]:
    """Return (category, subcategory), reusing cached values when available."""
    cached = _get_cached_taxonomy(document)
    if cached is not None:
        return cached

    content_text = await _resolve_document_text(session, document)
    category, subcategory = await generate_ai_taxonomy(
        document.title, content_text, llm
    )
    _set_cached_taxonomy(document, category, subcategory)
    return category, subcategory


async def ai_sort_document(
    session: AsyncSession,
    document: Document,
    llm,
) -> Document:
    """Sort a single document into the 4-level AI folder hierarchy."""
    connector: SearchSourceConnector | None = None
    if document.connector_id is not None:
        connector = await session.get(SearchSourceConnector, document.connector_id)

    root_label = resolve_root_folder_label(document, connector)
    date_label = resolve_date_folder(document)

    category, subcategory = await _resolve_taxonomy(session, document, llm)

    segments = _build_path_segments(root_label, date_label, category, subcategory)

    leaf_folder = await ensure_folder_hierarchy_with_depth_validation(
        session,
        document.search_space_id,
        segments,
    )

    document.folder_id = leaf_folder.id
    await session.flush()
    return document


async def ai_sort_all_documents(
    session: AsyncSession,
    search_space_id: int,
    llm,
) -> tuple[int, int]:
    """Sort all documents in a search space. Returns (sorted_count, failed_count)."""
    stmt = (
        select(Document)
        .where(Document.search_space_id == search_space_id)
        .options(selectinload(Document.connector))
    )
    result = await session.execute(stmt)
    documents = list(result.scalars().all())

    sorted_count = 0
    failed_count = 0

    for doc in documents:
        try:
            connector = doc.connector
            root_label = resolve_root_folder_label(doc, connector)
            date_label = resolve_date_folder(doc)

            category, subcategory = await _resolve_taxonomy(session, doc, llm)
            segments = _build_path_segments(
                root_label, date_label, category, subcategory
            )

            leaf_folder = await ensure_folder_hierarchy_with_depth_validation(
                session,
                search_space_id,
                segments,
            )
            doc.folder_id = leaf_folder.id
            sorted_count += 1
        except Exception:
            logger.error("Failed to AI-sort document %s", doc.id, exc_info=True)
            failed_count += 1

    await session.commit()
    logger.info(
        "AI sort complete for search_space=%d: sorted=%d, failed=%d",
        search_space_id,
        sorted_count,
        failed_count,
    )
    return sorted_count, failed_count
