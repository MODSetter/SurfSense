"""
Web search tool for the SurfSense agent.

Provides a unified tool for real-time web searches that dispatches to all
configured search engines: the platform SearXNG instance (always available)
plus any user-configured live-search connectors (Tavily, Linkup, Baidu).
"""

import asyncio
import json
import time
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.db import shielded_async_session
from app.services.connector_service import ConnectorService
from app.utils.perf import get_perf_logger

_LIVE_SEARCH_CONNECTORS: set[str] = {
    "TAVILY_API",
    "LINKUP_API",
    "BAIDU_SEARCH_API",
}

_LIVE_CONNECTOR_SPECS: dict[str, tuple[str, bool, bool, dict[str, Any]]] = {
    "TAVILY_API": ("search_tavily", False, True, {}),
    "LINKUP_API": ("search_linkup", False, False, {"mode": "standard"}),
    "BAIDU_SEARCH_API": ("search_baidu", False, True, {}),
}

_CONNECTOR_LABELS: dict[str, str] = {
    "TAVILY_API": "Tavily",
    "LINKUP_API": "Linkup",
    "BAIDU_SEARCH_API": "Baidu",
}


class WebSearchInput(BaseModel):
    """Input schema for the web_search tool."""

    query: str = Field(
        description="The search query to look up on the web. Use specific, descriptive terms.",
    )
    top_k: int = Field(
        default=10,
        description="Number of results to retrieve (default: 10, max: 50).",
    )


def _format_web_results(
    documents: list[dict[str, Any]],
    *,
    max_chars: int = 50_000,
) -> str:
    """Format web search results into XML suitable for the LLM context."""
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
        source = metadata.get("document_type") or doc.get("source") or "WEB_SEARCH"
        if not content:
            continue

        metadata_json = json.dumps(metadata, ensure_ascii=False)
        doc_xml = "\n".join(
            [
                "<document>",
                "<document_metadata>",
                f"  <document_type>{source}</document_type>",
                f"  <title><![CDATA[{title}]]></title>",
                f"  <url><![CDATA[{url}]]></url>",
                f"  <metadata_json><![CDATA[{metadata_json}]]></metadata_json>",
                "</document_metadata>",
                "<document_content>",
                f"  <chunk id='{url}'><![CDATA[{content}]]></chunk>",
                "</document_content>",
                "</document>",
                "",
            ]
        )

        if total_chars + len(doc_xml) > max_chars:
            parts.append("<!-- Output truncated to fit context window -->")
            break

        parts.append(doc_xml)
        total_chars += len(doc_xml)

    return "\n".join(parts).strip() or "No web search results found."


async def _search_live_connector(
    connector: str,
    query: str,
    search_space_id: int,
    top_k: int,
    semaphore: asyncio.Semaphore,
) -> list[dict[str, Any]]:
    """Dispatch a single live-search connector (Tavily / Linkup / Baidu)."""
    perf = get_perf_logger()
    spec = _LIVE_CONNECTOR_SPECS.get(connector)
    if spec is None:
        return []

    method_name, _includes_date_range, includes_top_k, extra_kwargs = spec
    kwargs: dict[str, Any] = {
        "user_query": query,
        "search_space_id": search_space_id,
        **extra_kwargs,
    }
    if includes_top_k:
        kwargs["top_k"] = top_k

    try:
        t0 = time.perf_counter()
        async with semaphore, shielded_async_session() as session:
            svc = ConnectorService(session, search_space_id)
            _, chunks = await getattr(svc, method_name)(**kwargs)
            perf.info(
                "[web_search] connector=%s results=%d in %.3fs",
                connector,
                len(chunks),
                time.perf_counter() - t0,
            )
            return chunks
    except Exception as e:
        perf.warning("[web_search] connector=%s FAILED: %s", connector, e)
        return []


def create_web_search_tool(
    search_space_id: int | None = None,
    available_connectors: list[str] | None = None,
) -> StructuredTool:
    """Factory for the ``web_search`` tool.

    Dispatches in parallel to the platform SearXNG instance and any
    user-configured live-search connectors (Tavily, Linkup, Baidu).
    """
    active_live_connectors: list[str] = []
    if available_connectors:
        active_live_connectors = [
            c for c in available_connectors if c in _LIVE_SEARCH_CONNECTORS
        ]

    engine_names = ["SearXNG (platform default)"]
    engine_names.extend(_CONNECTOR_LABELS.get(c, c) for c in active_live_connectors)
    engines_summary = ", ".join(engine_names)

    description = (
        "Search the web for real-time information. "
        "Use this for current events, news, prices, weather, public facts, or any "
        "question that requires up-to-date information from the internet.\n\n"
        f"Active search engines: {engines_summary}.\n"
        "All configured engines are queried in parallel and results are merged."
    )

    _search_space_id = search_space_id
    _active_live = active_live_connectors

    async def _web_search_impl(query: str, top_k: int = 10) -> str:
        from app.services import web_search_service

        perf = get_perf_logger()
        t0 = time.perf_counter()
        clamped_top_k = min(max(1, top_k), 50)

        semaphore = asyncio.Semaphore(4)
        tasks: list[asyncio.Task[list[dict[str, Any]]]] = []

        if web_search_service.is_available():

            async def _searxng() -> list[dict[str, Any]]:
                async with semaphore:
                    _result_obj, docs = await web_search_service.search(
                        query=query,
                        top_k=clamped_top_k,
                    )
                    return docs

            tasks.append(asyncio.ensure_future(_searxng()))

        if _search_space_id is not None:
            for connector in _active_live:
                tasks.append(
                    asyncio.ensure_future(
                        _search_live_connector(
                            connector=connector,
                            query=query,
                            search_space_id=_search_space_id,
                            top_k=clamped_top_k,
                            semaphore=semaphore,
                        )
                    )
                )

        if not tasks:
            return "Web search is not available — no search engines are configured."

        results_lists = await asyncio.gather(*tasks, return_exceptions=True)

        all_documents: list[dict[str, Any]] = []
        for result in results_lists:
            if isinstance(result, BaseException):
                perf.warning("[web_search] a search engine failed: %s", result)
                continue
            all_documents.extend(result)

        seen_urls: set[str] = set()
        deduplicated: list[dict[str, Any]] = []
        for doc in all_documents:
            url = ((doc.get("document") or {}).get("metadata") or {}).get("url", "")
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            deduplicated.append(doc)

        formatted = _format_web_results(deduplicated)

        perf.info(
            "[web_search] query=%r engines=%d results=%d deduped=%d chars=%d in %.3fs",
            query[:60],
            len(tasks),
            len(all_documents),
            len(deduplicated),
            len(formatted),
            time.perf_counter() - t0,
        )
        return formatted

    return StructuredTool(
        name="web_search",
        description=description,
        coroutine=_web_search_impl,
        args_schema=WebSearchInput,
    )
