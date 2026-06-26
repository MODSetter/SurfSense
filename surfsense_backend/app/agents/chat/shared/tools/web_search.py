"""
Web search tool for the SurfSense agent.

Provides a unified tool for real-time web searches that dispatches to all
configured search engines: the platform SearXNG instance (always available)
plus any user-configured live-search connectors (Tavily, Linkup, Baidu).

Each result is registered into the conversation citation registry as a
``WEB_RESULT`` and rendered with a server-assigned ``[n]`` label, so the model
cites the web exactly like the knowledge base — one ``[n]`` spine, no special
web citation form.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Annotated, Any
from urllib.parse import urlparse

from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.types import Command

from app.db import shielded_async_session
from app.services.connector_service import ConnectorService
from app.utils.perf import get_perf_logger

if TYPE_CHECKING:
    from app.agents.chat.multi_agent_chat.shared.document_render import (
        RenderableDocument,
    )

# NOTE: imports from ``app.agents.chat.multi_agent_chat`` are done lazily inside
# the functions below. This module lives under ``app.agents.chat.shared`` but is
# imported during the ``multi_agent_chat`` package's own init cascade (via the
# research subagent); importing that package at module load would re-enter a
# partially-initialized module. Lazy imports break that cycle.

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


def _web_source_label(url: str) -> str:
    """A compact, human-readable source for the ``<document source=…>`` attr."""
    domain = urlparse(url).netloc.removeprefix("www.") if url else ""
    return f"Web · {domain}" if domain else "Web"


def _to_renderable_web_documents(
    documents: list[dict[str, Any]],
    *,
    max_chars: int = 50_000,
) -> list[RenderableDocument]:
    """Map raw web results to renderable documents, one passage (the snippet) each.

    A result with no URL is skipped: ``url`` is the citation locator, so without
    it the result cannot be registered or resolved.
    """
    from app.agents.chat.multi_agent_chat.shared.citations import CitationSourceType
    from app.agents.chat.multi_agent_chat.shared.document_render import (
        RenderableDocument,
        RenderablePassage,
    )

    renderables: list[RenderableDocument] = []
    total_chars = 0

    for doc in documents:
        doc_info = doc.get("document") or {}
        metadata = doc_info.get("metadata") or {}
        title = doc_info.get("title") or "Web Result"
        url = metadata.get("url") or ""
        content = (doc.get("content") or "").strip()
        if not content or not url:
            continue

        total_chars += len(content)
        if total_chars > max_chars:
            break

        renderables.append(
            RenderableDocument(
                title=title,
                source=_web_source_label(url),
                passages=[
                    RenderablePassage(
                        content=content,
                        locator={"url": url},
                        source_type=CitationSourceType.WEB_RESULT,
                    )
                ],
            )
        )

    return renderables


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
) -> BaseTool:
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

    async def _web_search_impl(
        query: Annotated[
            str,
            "The search query to look up on the web. Use specific, descriptive terms.",
        ],
        runtime: ToolRuntime,
        top_k: Annotated[
            int,
            "Number of results to retrieve (default: 10, max: 50).",
        ] = 10,
    ) -> Command | str:
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

        from app.agents.chat.multi_agent_chat.shared.citations import load_registry
        from app.agents.chat.multi_agent_chat.shared.document_render import (
            render_web_results,
        )

        registry = load_registry(getattr(runtime, "state", None))
        renderables = _to_renderable_web_documents(deduplicated)
        rendered = render_web_results(renderables, registry)

        perf.info(
            "[web_search] query=%r engines=%d results=%d deduped=%d renderable=%d in %.3fs",
            query[:60],
            len(tasks),
            len(all_documents),
            len(deduplicated),
            len(renderables),
            time.perf_counter() - t0,
        )

        if rendered is None:
            return "No web search results found."

        return Command(
            update={
                "messages": [
                    ToolMessage(content=rendered, tool_call_id=runtime.tool_call_id)
                ],
                "citation_registry": registry,
            }
        )

    return StructuredTool.from_function(
        name="web_search",
        description=description,
        coroutine=_web_search_impl,
    )
