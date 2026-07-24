"""Knowledge-base read tools: semantic search, list, and read one document.

Search and list default to the active workspace; a document read is addressed by
id, which is unique across the account, so it needs no workspace.
"""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ...core.client import SurfSenseClient
from ...core.rendering import ResponseFormatParam, clip, to_json
from ...core.workspace_context import WorkspaceContext, WorkspaceParam
from .annotations import READ, DocumentId, DocumentTypes


def register(mcp: FastMCP, client: SurfSenseClient, context: WorkspaceContext) -> None:
    """Register the knowledge-base read tools."""

    @mcp.tool(
        name="surfsense_search_knowledge_base",
        title="Search knowledge base",
        annotations=READ,
        structured_output=False,
    )
    async def search_knowledge_base(
        query: Annotated[
            str,
            Field(
                min_length=1,
                description="Natural-language search, e.g. "
                "'notebooklm user complaints'.",
            ),
        ],
        top_k: Annotated[
            int, Field(ge=1, le=20, description="Maximum documents to return.")
        ] = 5,
        document_types: DocumentTypes = None,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Search the workspace's knowledge base by meaning and keywords.

        Use this FIRST when a question might be answered by content already
        stored in SurfSense — notes, uploaded files, saved pages, past
        research. Do NOT use it to fetch new data from the web; use the
        scraper tools for that. Returns the most relevant documents with the
        passages that matched, ranked by relevance score.
        Example: query='pricing feedback', top_k=5.
        """
        resolved = await context.resolve(workspace)
        hits = await client.request(
            "POST",
            "/documents/search-semantic",
            json={
                "workspace_id": resolved.id,
                "query": query,
                "top_k": max(1, min(top_k, 20)),
                "document_types": document_types,
            },
        )
        items = (hits or {}).get("items", [])
        if response_format == "json":
            return to_json(items)
        return _render_search(query, items)

    @mcp.tool(
        name="surfsense_list_documents",
        title="List documents",
        annotations=READ,
        structured_output=False,
    )
    async def list_documents(
        document_types: DocumentTypes = None,
        folder_id: Annotated[
            int | None,
            Field(description="Only documents in this folder. Omit for all."),
        ] = None,
        page: Annotated[int, Field(ge=0, description="Zero-based page number.")] = 0,
        page_size: Annotated[int, Field(ge=1, description="Documents per page.")] = 20,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """List documents in the workspace's knowledge base, newest first.

        Use this to browse or inventory what is stored; to find documents
        about a topic, prefer surfsense_search_knowledge_base. Returns each
        document's title, id, type, and update time, plus a has_more flag —
        request the next page by increasing page.
        Example: document_types=['FILE'], page=0, page_size=20.
        """
        resolved = await context.resolve(workspace)
        result = await client.request(
            "GET",
            "/documents",
            params={
                "workspace_id": resolved.id,
                "page": page,
                "page_size": page_size,
                "document_types": _join(document_types),
                "folder_id": folder_id,
            },
        )
        if response_format == "json":
            return to_json(result)
        return _render_document_list(result)

    @mcp.tool(
        name="surfsense_get_document",
        title="Read one document",
        annotations=READ,
        structured_output=False,
    )
    async def get_document(
        document_id: DocumentId,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Read one document's full content and metadata by id.

        Use this after surfsense_search_knowledge_base or
        surfsense_list_documents to open a specific document — search results
        only include the matching passages, this returns the whole text.
        The markdown form is an Open Knowledge Format (OKF) concept: a YAML
        frontmatter block (type, title, tags, resource, timestamp) followed by
        the document body.
        """
        if response_format == "json":
            document = await client.request("GET", f"/documents/{document_id}")
            return clip(to_json(document))
        concept = await client.request(
            "GET",
            f"/documents/{document_id}",
            headers={"Accept": "text/markdown"},
        )
        return clip(concept if isinstance(concept, str) else str(concept))


def _join(values: list[str] | None) -> str | None:
    return ",".join(values) if values else None


def _render_search(query: str, items: list[dict]) -> str:
    if not items:
        return f'No matches for "{query}".'
    lines = [f'# {len(items)} result(s) for "{query}"', ""]
    for hit in items:
        lines.append(
            f"## {hit.get('title', 'Untitled')} "
            f"(id {hit.get('document_id')}) — score {hit.get('score', 0):.3f}"
        )
        for chunk in hit.get("chunks", []):
            excerpt = clip(chunk.get("content", "").strip(), 500)
            lines.append(f"> {excerpt}")
        lines.append("")
    return "\n".join(lines).strip()


def _render_document_list(result: dict | None) -> str:
    items = (result or {}).get("items", [])
    if not items:
        return "No documents found."
    lines = ["# Documents", ""]
    for doc in items:
        lines.append(
            f"- **{doc.get('title', 'Untitled')}** (id {doc.get('id')}) · "
            f"{doc.get('document_type')} · updated {doc.get('updated_at')}"
        )
    total = (result or {}).get("total", len(items))
    page = (result or {}).get("page", 0)
    has_more = (result or {}).get("has_more", False)
    lines.append("")
    lines.append(
        f"_Page {page} · showing {len(items)} of {total}"
        + (" · more available_" if has_more else "_")
    )
    return "\n".join(lines)
