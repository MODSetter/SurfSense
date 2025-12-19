"""
Test script for create_deep_agent with ChatLiteLLM from global_llm_config.yaml

This demonstrates:
1. Loading LLM config from global_llm_config.yaml
2. Creating a ChatLiteLLM instance
3. Using context_schema to add custom state fields
4. Creating a search_knowledge_base tool similar to fetch_relevant_documents
"""

import sys
from pathlib import Path

# Add parent directory to path so 'app' module can be found when running directly
_THIS_FILE = Path(__file__).resolve()
_BACKEND_ROOT = _THIS_FILE.parent.parent.parent.parent  # surfsense_backend/
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any, TypedDict

import yaml
from deepagents import create_deep_agent
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_litellm import ChatLiteLLM
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_maker
from app.services.connector_service import ConnectorService

# =============================================================================
# LLM Configuration Loading
# =============================================================================


def load_llm_config_from_yaml(llm_config_id: int = -1) -> dict | None:
    """
    Load a specific LLM config from global_llm_config.yaml.

    Args:
        llm_config_id: The id of the config to load (default: -1)

    Returns:
        LLM config dict or None if not found
    """
    # Get the config file path
    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    config_file = base_dir / "app" / "config" / "global_llm_config.yaml"

    # Fallback to example file if main config doesn't exist
    if not config_file.exists():
        config_file = base_dir / "app" / "config" / "global_llm_config.example.yaml"
        if not config_file.exists():
            print("Error: No global_llm_config.yaml or example file found")
            return None

    try:
        with open(config_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
            configs = data.get("global_llm_configs", [])
            for cfg in configs:
                if isinstance(cfg, dict) and cfg.get("id") == llm_config_id:
                    return cfg

            print(f"Error: Global LLM config id {llm_config_id} not found")
            return None
    except Exception as e:
        print(f"Error loading config: {e}")
        return None


def create_chat_litellm_from_config(llm_config: dict) -> ChatLiteLLM | None:
    """
    Create a ChatLiteLLM instance from a global LLM config.

    Args:
        llm_config: LLM configuration dictionary from YAML

    Returns:
        ChatLiteLLM instance or None on error
    """
    # Provider mapping (same as in llm_service.py)
    provider_map = {
        "OPENAI": "openai",
        "ANTHROPIC": "anthropic",
        "GROQ": "groq",
        "COHERE": "cohere",
        "GOOGLE": "gemini",
        "OLLAMA": "ollama",
        "MISTRAL": "mistral",
        "AZURE_OPENAI": "azure",
        "OPENROUTER": "openrouter",
        "XAI": "xai",
        "BEDROCK": "bedrock",
        "VERTEX_AI": "vertex_ai",
        "TOGETHER_AI": "together_ai",
        "FIREWORKS_AI": "fireworks_ai",
        "DEEPSEEK": "openai",
        "ALIBABA_QWEN": "openai",
        "MOONSHOT": "openai",
        "ZHIPU": "openai",
    }

    # Build the model string
    if llm_config.get("custom_provider"):
        model_string = f"{llm_config['custom_provider']}/{llm_config['model_name']}"
    else:
        provider = llm_config.get("provider", "").upper()
        provider_prefix = provider_map.get(provider, provider.lower())
        model_string = f"{provider_prefix}/{llm_config['model_name']}"

    # Create ChatLiteLLM instance
    litellm_kwargs = {
        "model": model_string,
        "api_key": llm_config.get("api_key"),
    }

    # Add optional parameters
    if llm_config.get("api_base"):
        litellm_kwargs["api_base"] = llm_config["api_base"]

    # Add any additional litellm parameters
    if llm_config.get("litellm_params"):
        litellm_kwargs.update(llm_config["litellm_params"])

    return ChatLiteLLM(**litellm_kwargs)


# =============================================================================
# Custom Context Schema
# =============================================================================


class SurfSenseContextSchema(TypedDict):
    """
    Custom state schema for the SurfSense deep agent.

    This extends the default agent state with custom fields.
    The default state already includes:
    - messages: Conversation history
    - todos: Task list from TodoListMiddleware
    - files: Virtual filesystem from FilesystemMiddleware

    We're adding fields needed for knowledge base search:
    - search_space_id: The user's search space ID
    - db_session: Database session (injected at runtime)
    - connector_service: Connector service instance (injected at runtime)
    """

    search_space_id: int
    # These are runtime-injected and won't be serialized
    # db_session and connector_service are passed when invoking the agent


# =============================================================================
# Knowledge Base Search Tool
# =============================================================================

# Canonical connector values used internally by ConnectorService
_ALL_CONNECTORS: list[str] = [
    "EXTENSION",
    "FILE",
    "SLACK_CONNECTOR",
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
]


def _normalize_connectors(connectors_to_search: list[str] | None) -> list[str]:
    """
    Normalize connectors provided by the model.

    - Accepts user-facing enums like WEBCRAWLER_CONNECTOR and maps them to canonical
      ConnectorService types.
    - Drops unknown values.
    - If None/empty, defaults to searching across all known connectors.
    """
    if not connectors_to_search:
        return list(_ALL_CONNECTORS)

    normalized: list[str] = []
    for raw in connectors_to_search:
        c = (raw or "").strip().upper()
        if not c:
            continue
        if c == "WEBCRAWLER_CONNECTOR":
            c = "CRAWLED_URL"
        normalized.append(c)

    # de-dupe while preserving order + filter unknown
    seen: set[str] = set()
    out: list[str] = []
    for c in normalized:
        if c in seen:
            continue
        if c not in _ALL_CONNECTORS:
            continue
        seen.add(c)
        out.append(c)
    return out if out else list(_ALL_CONNECTORS)


SURFSENSE_CITATION_INSTRUCTIONS = """
<citation_instructions>
CRITICAL CITATION REQUIREMENTS:

1. For EVERY piece of information you include from the documents, add a citation in the format [citation:chunk_id] where chunk_id is the exact value from the `<chunk id='...'>` tag inside `<document_content>`.
2. Make sure ALL factual statements from the documents have proper citations.
3. If multiple chunks support the same point, include all relevant citations [citation:chunk_id1], [citation:chunk_id2].
4. You MUST use the exact chunk_id values from the `<chunk id='...'>` attributes. Do not create your own citation numbers.
5. Every citation MUST be in the format [citation:chunk_id] where chunk_id is the exact chunk id value.
6. Never modify or change the chunk_id - always use the original values exactly as provided in the chunk tags.
7. Do not return citations as clickable links.
8. Never format citations as markdown links like "([citation:5](https://example.com))". Always use plain square brackets only.
9. Citations must ONLY appear as [citation:chunk_id] or [citation:chunk_id1], [citation:chunk_id2] format - never with parentheses, hyperlinks, or other formatting.
10. Never make up chunk IDs. Only use chunk_id values that are explicitly provided in the `<chunk id='...'>` tags.
11. If you are unsure about a chunk_id, do not include a citation rather than guessing or making one up.

<document_structure_example>
The documents you receive are structured like this:

<document>
<document_metadata>
  <document_id>42</document_id>
  <document_type>GITHUB_CONNECTOR</document_type>
  <title><![CDATA[Some repo / file / issue title]]></title>
  <url><![CDATA[https://example.com]]></url>
  <metadata_json><![CDATA[{{"any":"other metadata"}}]]></metadata_json>
</document_metadata>

<document_content>
  <chunk id='123'><![CDATA[First chunk text...]]></chunk>
  <chunk id='124'><![CDATA[Second chunk text...]]></chunk>
</document_content>
</document>

IMPORTANT: You MUST cite using the chunk ids (e.g. 123, 124). Do NOT cite document_id.
</document_structure_example>

<citation_format>
- Every fact from the documents must have a citation in the format [citation:chunk_id] where chunk_id is the EXACT id value from a `<chunk id='...'>` tag
- Citations should appear at the end of the sentence containing the information they support
- Multiple citations should be separated by commas: [citation:chunk_id1], [citation:chunk_id2], [citation:chunk_id3]
- No need to return references section. Just citations in answer.
- NEVER create your own citation format - use the exact chunk_id values from the documents in the [citation:chunk_id] format
- NEVER format citations as clickable links or as markdown links like "([citation:5](https://example.com))". Always use plain square brackets only
- NEVER make up chunk IDs if you are unsure about the chunk_id. It is better to omit the citation than to guess
</citation_format>

<citation_examples>
CORRECT citation formats:
- [citation:5]
- [citation:chunk_id1], [citation:chunk_id2], [citation:chunk_id3]

INCORRECT citation formats (DO NOT use):
- Using parentheses and markdown links: ([citation:5](https://github.com/MODSetter/SurfSense))
- Using parentheses around brackets: ([citation:5])
- Using hyperlinked text: [link to source 5](https://example.com)
- Using footnote style: ... library¹
- Making up source IDs when source_id is unknown
- Using old IEEE format: [1], [2], [3]
- Using source types instead of IDs: [citation:GITHUB_CONNECTOR] instead of [citation:5]
</citation_examples>

<citation_output_example>
Based on your GitHub repositories and video content, Python's asyncio library provides tools for writing concurrent code using the async/await syntax [citation:5]. It's particularly useful for I/O-bound and high-level structured network code [citation:5].

The key advantage of asyncio is that it can improve performance by allowing other code to run while waiting for I/O operations to complete [citation:12]. This makes it excellent for scenarios like web scraping, API calls, database operations, or any situation where your program spends time waiting for external resources.

However, from your video learning, it's important to note that asyncio is not suitable for CPU-bound tasks as it runs on a single thread [citation:12]. For computationally intensive work, you'd want to use multiprocessing instead.
</citation_output_example>
</citation_instructions>
"""


def _parse_date_or_datetime(value: str) -> datetime:
    """
    Parse either an ISO date (YYYY-MM-DD) or ISO datetime into an aware UTC datetime.

    - If `value` is a date, interpret it as start-of-day in UTC.
    - If `value` is a datetime without timezone, assume UTC.
    """
    raw = (value or "").strip()
    if not raw:
        raise ValueError("Empty date string")

    # Date-only
    if "T" not in raw:
        d = datetime.fromisoformat(raw).date()
        return datetime(d.year, d.month, d.day, tzinfo=UTC)

    # Datetime (may be naive)
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _resolve_date_range(
    start_date: datetime | None,
    end_date: datetime | None,
) -> tuple[datetime, datetime]:
    """
    Resolve a date range, defaulting to the last 2 years if not provided.
    Ensures start_date <= end_date.
    """
    resolved_end = end_date or datetime.now(UTC)
    resolved_start = start_date or (resolved_end - timedelta(days=730))

    if resolved_start > resolved_end:
        resolved_start, resolved_end = resolved_end, resolved_start

    return resolved_start, resolved_end


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


async def search_knowledge_base_async(
    query: str,
    search_space_id: int,
    db_session: AsyncSession,
    connector_service: ConnectorService,
    connectors_to_search: list[str] | None = None,
    top_k: int = 10,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
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

    Returns:
        Formatted string with search results
    """
    all_documents = []

    # Resolve date range (default last 2 years)
    resolved_start_date, resolved_end_date = _resolve_date_range(
        start_date=start_date,
        end_date=end_date,
    )

    connectors = _normalize_connectors(connectors_to_search)

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


def create_search_knowledge_base_tool(
    search_space_id: int,
    db_session: AsyncSession,
    connector_service: ConnectorService,
):
    """
    Factory function to create the search_knowledge_base tool with injected dependencies.

    Args:
        search_space_id: The user's search space ID
        db_session: Database session
        connector_service: Initialized connector service
        connectors_to_search: List of connector types to search

    Returns:
        A configured tool function
    """

    @tool
    async def search_knowledge_base(
        query: str,
        top_k: int = 10,
        start_date: str | None = None,
        end_date: str | None = None,
        connectors_to_search: list[str] | None = None,
    ) -> str:
        """
        Search the user's personal knowledge base for relevant information.

        Use this tool to find documents, notes, files, web pages, and other content
        that may help answer the user's question.

        IMPORTANT:
        - If the user requests a specific source type (e.g. "my notes", "Slack messages"),
          pass `connectors_to_search=[...]` using the enums below.
        - If `connectors_to_search` is omitted/empty, the system will search broadly.

        ## Available connector enums for `connectors_to_search`

        - EXTENSION: "Web content saved via SurfSense browser extension" (personal browsing history)
        - FILE: "User-uploaded documents (PDFs, Word, etc.)" (personal files)
        - NOTE: "SurfSense Notes" (notes created inside SurfSense)
        - SLACK_CONNECTOR: "Slack conversations and shared content" (personal workspace communications)
        - NOTION_CONNECTOR: "Notion workspace pages and databases" (personal knowledge management)
        - YOUTUBE_VIDEO: "YouTube video transcripts and metadata" (personally saved videos)
        - GITHUB_CONNECTOR: "GitHub repository content and issues" (personal repositories and interactions)
        - ELASTICSEARCH_CONNECTOR: "Elasticsearch indexed documents and data" (personal Elasticsearch instances and custom data sources)
        - LINEAR_CONNECTOR: "Linear project issues and discussions" (personal project management)
        - JIRA_CONNECTOR: "Jira project issues, tickets, and comments" (personal project tracking)
        - CONFLUENCE_CONNECTOR: "Confluence pages and comments" (personal project documentation)
        - CLICKUP_CONNECTOR: "ClickUp tasks and project data" (personal task management)
        - GOOGLE_CALENDAR_CONNECTOR: "Google Calendar events, meetings, and schedules" (personal calendar and time management)
        - GOOGLE_GMAIL_CONNECTOR: "Google Gmail emails and conversations" (personal emails and communications)
        - DISCORD_CONNECTOR: "Discord server conversations and shared content" (personal community communications)
        - AIRTABLE_CONNECTOR: "Airtable records, tables, and database content" (personal data management and organization)
        - TAVILY_API: "Tavily search API results" (personalized search results)
        - SEARXNG_API: "SearxNG search API results" (personalized search results)
        - LINKUP_API: "Linkup search API results" (personalized search results)
        - BAIDU_SEARCH_API: "Baidu search API results" (personalized search results)
        - LUMA_CONNECTOR: "Luma events"
        - WEBCRAWLER_CONNECTOR: "Webpages indexed by SurfSense" (personally selected websites)
        - BOOKSTACK_CONNECTOR: "BookStack pages" (personal documentation)

        NOTE: `WEBCRAWLER_CONNECTOR` is mapped internally to the canonical document type `CRAWLED_URL`.

        Args:
            query: The search query - be specific and include key terms
            top_k: Number of results to retrieve (default: 10)
            start_date: Optional ISO date/datetime (e.g. "2025-12-12" or "2025-12-12T00:00:00+00:00")
            end_date: Optional ISO date/datetime (e.g. "2025-12-19" or "2025-12-19T23:59:59+00:00")
            connectors_to_search: Optional list of connector enums to search. If omitted, searches all.

        Returns:
            Formatted string with relevant documents and their content
        """
        parsed_start: datetime | None = None
        parsed_end: datetime | None = None

        if start_date:
            parsed_start = _parse_date_or_datetime(start_date)
        if end_date:
            parsed_end = _parse_date_or_datetime(end_date)

        return await search_knowledge_base_async(
            query=query,
            search_space_id=search_space_id,
            db_session=db_session,
            connector_service=connector_service,
            connectors_to_search=connectors_to_search,
            top_k=top_k,
            start_date=parsed_start,
            end_date=parsed_end,
        )

    return search_knowledge_base


# =============================================================================
# System Prompt
# =============================================================================


def build_surfsense_system_prompt(today: datetime | None = None) -> str:
    resolved_today = (today or datetime.now(UTC)).astimezone(UTC).date().isoformat()

    return f"""
<system_instruction>
You are SurfSense, a reasoning and acting AI agent designed to answer user questions using the user's personal knowledge base.

Today's date (UTC): {resolved_today}

</system_instruction>
<tools>
You have access to the following tools:
- search_knowledge_base: Search the user's personal knowledge base for relevant information.
  - Args:
    - query: The search query - be specific and include key terms
    - top_k: Number of results to retrieve (default: 10)
    - start_date: Optional ISO date/datetime (e.g. "2025-12-12" or "2025-12-12T00:00:00+00:00")
    - end_date: Optional ISO date/datetime (e.g. "2025-12-19" or "2025-12-19T23:59:59+00:00")
    - connectors_to_search: Optional list of connector enums to search. If omitted, searches all.
  - Returns: Formatted string with relevant documents and their content
</tools>
<tool_call_examples>
- User: "Fetch all my notes and what's in them?"
  - Call: `search_knowledge_base(query="*", top_k=50, connectors_to_search=["NOTE"])`

- User: "What did I discuss on Slack last week about the React migration?"
  - Call: `search_knowledge_base(query="React migration", connectors_to_search=["SLACK_CONNECTOR"], start_date="YYYY-MM-DD", end_date="YYYY-MM-DD")`
</tool_call_examples>

{SURFSENSE_CITATION_INSTRUCTIONS}
"""


SURFSENSE_SYSTEM_PROMPT = build_surfsense_system_prompt()


# =============================================================================
# Deep Agent Factory
# =============================================================================


def create_surfsense_deep_agent(
    llm: ChatLiteLLM,
    search_space_id: int,
    db_session: AsyncSession,
    connector_service: ConnectorService,
):
    """
    Create a SurfSense deep agent with knowledge base search capability.

    Args:
        llm: ChatLiteLLM instance
        search_space_id: The user's search space ID
        db_session: Database session
        connector_service: Initialized connector service
        connectors_to_search: List of connector types to search (default: common connectors)

    Returns:
        CompiledStateGraph: The configured deep agent
    """
    # Create the search tool with injected dependencies
    search_tool = create_search_knowledge_base_tool(
        search_space_id=search_space_id,
        db_session=db_session,
        connector_service=connector_service,
    )

    # Create the deep agent
    agent = create_deep_agent(
        model=llm,
        tools=[search_tool],
        system_prompt=build_surfsense_system_prompt(),
        context_schema=SurfSenseContextSchema,
    )

    return agent


# =============================================================================
# Test Runner
# =============================================================================


async def run_test():
    """Run a basic test of the deep agent."""
    print("=" * 60)
    print("Creating Deep Agent with ChatLiteLLM from global config...")
    print("=" * 60)

    # Create ChatLiteLLM from global config
    # Use global LLM config by id (negative ids are reserved for global configs)
    llm_config = load_llm_config_from_yaml(llm_config_id=-2)
    if not llm_config:
        raise ValueError("Failed to load LLM config from YAML")
    llm = create_chat_litellm_from_config(llm_config)
    if not llm:
        raise ValueError("Failed to create ChatLiteLLM instance")

    # Create a real DB session + ConnectorService, then build the full SurfSense agent.
    async with async_session_maker() as session:
        # Use the known dev search space id
        search_space_id = 5

        connector_service = ConnectorService(session, search_space_id=search_space_id)

        agent = create_surfsense_deep_agent(
            llm=llm,
            search_space_id=search_space_id,
            db_session=session,
            connector_service=connector_service,
        )

        print("\nAgent created successfully!")
        print(f"Agent type: {type(agent)}")

        # Invoke the agent with initial state
        print("\n" + "=" * 60)
        print("Invoking SurfSense agent (create_surfsense_deep_agent)...")
        print("=" * 60)

        initial_state = {
            "messages": [HumanMessage(content=("What are my notes from last 3 days?"))],
            "search_space_id": search_space_id,
        }

        print(f"\nUsing search_space_id: {search_space_id}")

        result = await agent.ainvoke(initial_state)

    print("\n" + "=" * 60)
    print("Agent Response:")
    print("=" * 60)

    # Print the response
    if "messages" in result:
        for msg in result["messages"]:
            msg_type = type(msg).__name__
            content = msg.content if hasattr(msg, "content") else str(msg)
            print(f"\n--- [{msg_type}] ---\n{content}\n")

    return result


if __name__ == "__main__":
    asyncio.run(run_test())
