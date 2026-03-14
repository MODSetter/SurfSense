"""
Web search tool backed by the platform SearXNG instance.

Provides a standalone tool for real-time web searches, separate from the
knowledge base search which handles local/indexed documents.
"""

import json
import time
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.utils.perf import get_perf_logger


class WebSearchInput(BaseModel):
    """Input schema for the web_search tool."""

    query: str = Field(
        description="The search query to look up on the web. Use specific, descriptive terms.",
    )
    top_k: int = Field(
        default=10,
        description="Number of results to retrieve (default: 10, max: 50).",
    )


def _format_web_results(documents: list[dict[str, Any]], *, max_chars: int = 50_000) -> str:
    """Format SearXNG results into XML suitable for the LLM context."""
    if not documents:
        return "No web search results found."

    parts: list[str] = []
    total_chars = 0

    for doc in documents:
        doc_info = doc.get("document") or {}
        metadata = doc_info.get("metadata") or {}
        title = doc_info.get("title") or "Web Result"
        url = metadata.get("url") or ""
        content = (doc.get("content") or "").strip()
        if not content:
            continue

        metadata_json = json.dumps(metadata, ensure_ascii=False)
        doc_xml = "\n".join([
            "<document>",
            "<document_metadata>",
            f"  <document_type>SEARXNG_API</document_type>",
            f"  <title><![CDATA[{title}]]></title>",
            f"  <url><![CDATA[{url}]]></url>",
            f"  <metadata_json><![CDATA[{metadata_json}]]></metadata_json>",
            "</document_metadata>",
            "<document_content>",
            f"  <chunk id='{url}'><![CDATA[{content}]]></chunk>",
            "</document_content>",
            "</document>",
            "",
        ])

        if total_chars + len(doc_xml) > max_chars:
            parts.append("<!-- Output truncated to fit context window -->")
            break

        parts.append(doc_xml)
        total_chars += len(doc_xml)

    return "\n".join(parts).strip() or "No web search results found."


def create_web_search_tool() -> StructuredTool:
    """Factory for the ``web_search`` tool.

    The tool calls the platform SearXNG service (via ``web_search_service``)
    which handles caching, circuit breaking, and retries internally.
    """

    async def _web_search_impl(query: str, top_k: int = 10) -> str:
        from app.services import web_search_service

        perf = get_perf_logger()
        t0 = time.perf_counter()

        if not web_search_service.is_available():
            return "Web search is not available — SearXNG is not configured on this server."

        _result_obj, documents = await web_search_service.search(
            query=query,
            top_k=min(max(1, top_k), 50),
        )

        formatted = _format_web_results(documents)

        perf.info(
            "[web_search] query=%r results=%d chars=%d in %.3fs",
            query[:60],
            len(documents),
            len(formatted),
            time.perf_counter() - t0,
        )
        return formatted

    return StructuredTool(
        name="web_search",
        description=(
            "Search the web for real-time information using the platform SearXNG instance. "
            "Use this for current events, news, prices, weather, public facts, or any "
            "question that requires up-to-date information from the internet. "
            "Results are privacy-focused — all queries are proxied through the server."
        ),
        coroutine=_web_search_impl,
        args_schema=WebSearchInput,
    )
