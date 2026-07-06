"""Knowledge-base tools: search the KB and manage its documents.

Semantic search plus the document lifecycle — list, read, add text, upload a
file, update, and delete — over a workspace's knowledge base. Search and reads
default to the active workspace; document ids identify a single document across
the whole account, so id-addressed tools need no workspace.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from ...core.client import SurfSenseClient
from ...core.errors import ToolError
from ...core.rendering import ResponseFormat, clip, to_json
from ...core.workspace_context import WorkspaceContext
from .note_ingestion import build_note_document

_READ = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)
_WRITE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False
)
_DELETE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False
)


def register(
    mcp: FastMCP, client: SurfSenseClient, context: WorkspaceContext
) -> None:
    """Register the knowledge-base tools on the server."""

    @mcp.tool(
        name="surfsense_search_knowledge_base",
        annotations=_READ,
        structured_output=False,
    )
    async def search_knowledge_base(
        query: str,
        top_k: int = 5,
        document_types: list[str] | None = None,
        workspace: str | None = None,
        response_format: ResponseFormat = "markdown",
    ) -> str:
        """Search the workspace's knowledge base by meaning and keyword.

        Use this to answer questions from stored content: it returns the most
        relevant documents with the passages that matched, ranked by relevance.
        top_k caps documents (1–20). Optionally restrict to document_types.
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
        name="surfsense_list_documents", annotations=_READ, structured_output=False
    )
    async def list_documents(
        document_types: list[str] | None = None,
        folder_id: int | None = None,
        page: int = 0,
        page_size: int = 20,
        workspace: str | None = None,
        response_format: ResponseFormat = "markdown",
    ) -> str:
        """List documents in the workspace's knowledge base, newest first.

        Use this to browse or inventory what is stored. Optionally filter by
        document_types or a folder_id. Paginated: returns page_size items and a
        has_more flag; request the next page by increasing page.
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
        name="surfsense_get_document", annotations=_READ, structured_output=False
    )
    async def get_document(
        document_id: int, response_format: ResponseFormat = "markdown"
    ) -> str:
        """Read one document's full content and metadata by id.

        Use this after search or list to open a specific document. The id comes
        from those tools' results.
        """
        document = await client.request("GET", f"/documents/{document_id}")
        if response_format == "json":
            return clip(to_json(document))
        return _render_document(document)

    @mcp.tool(
        name="surfsense_add_document", annotations=_WRITE, structured_output=False
    )
    async def add_document(
        title: str,
        content: str,
        source_url: str | None = None,
        workspace: str | None = None,
    ) -> str:
        """Add a text or markdown note to the workspace's knowledge base.

        Use this to save notes, summaries, or snippets so they become
        searchable. The content is indexed asynchronously, so it may take a
        moment to appear in search. source_url optionally records where the text
        came from.
        """
        resolved = await context.resolve(workspace)
        await client.request(
            "POST",
            "/documents",
            json=build_note_document(
                workspace_id=resolved.id,
                title=title,
                content=content,
                source_url=source_url,
            ),
        )
        return (
            f"Queued '{title}' for indexing in '{resolved.name}'. "
            "It will be searchable once processing completes."
        )

    @mcp.tool(
        name="surfsense_upload_file", annotations=_WRITE, structured_output=False
    )
    async def upload_file(
        file_path: str,
        use_vision_llm: bool = False,
        workspace: str | None = None,
    ) -> str:
        """Upload a local file (PDF, doc, etc.) into the knowledge base.

        Use this to ingest a file from disk; it is parsed, chunked, and indexed
        asynchronously. Set use_vision_llm to read scanned or image-heavy files
        with a vision model (slower).
        """
        resolved = await context.resolve(workspace)
        payload = _read_upload(file_path)
        result = await client.request(
            "POST",
            "/documents/fileupload",
            data={
                "workspace_id": str(resolved.id),
                "use_vision_llm": str(use_vision_llm).lower(),
                "processing_mode": "basic",
            },
            files=[("files", payload)],
        )
        pending = (result or {}).get("pending_files", 0)
        skipped = (result or {}).get("skipped_duplicates", 0)
        note = " (already present, skipped)" if skipped and not pending else ""
        return (
            f"Uploaded '{Path(file_path).name}' to '{resolved.name}'{note}. "
            "It will be searchable once processing completes."
        )

    @mcp.tool(
        name="surfsense_update_document", annotations=_WRITE, structured_output=False
    )
    async def update_document(document_id: int, content: str) -> str:
        """Replace a document's stored content by id.

        Use this to correct or rewrite a document's text. Note: this updates the
        stored content; re-indexing of search chunks is not triggered by this
        call.
        """
        existing = await client.request("GET", f"/documents/{document_id}")
        await client.request(
            "PUT",
            f"/documents/{document_id}",
            json={
                "document_type": existing["document_type"],
                "workspace_id": existing["workspace_id"],
                "content": content,
            },
        )
        return f"Updated document {document_id} ('{existing.get('title', '')}')."

    @mcp.tool(
        name="surfsense_delete_document", annotations=_DELETE, structured_output=False
    )
    async def delete_document(document_id: int) -> str:
        """Delete a document from the knowledge base by id.

        Use this to permanently remove a document. Deletion runs in the
        background; the document stops appearing in searches immediately.
        """
        await client.request("DELETE", f"/documents/{document_id}")
        return f"Deleted document {document_id}."


def _read_upload(file_path: str) -> tuple[str, bytes, str]:
    path = Path(file_path).expanduser()
    if not path.is_file():
        raise ToolError(f"No file at '{file_path}'.")
    mime, _ = mimetypes.guess_type(path.name)
    return (path.name, path.read_bytes(), mime or "application/octet-stream")


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


def _render_document(document: dict) -> str:
    content = clip(document.get("content", "") or "(empty)")
    return (
        f"# {document.get('title', 'Untitled')} (id {document.get('id')})\n"
        f"- type: {document.get('document_type')}\n"
        f"- workspace: {document.get('workspace_id')}\n"
        f"- updated: {document.get('updated_at')}\n\n"
        f"{content}"
    )
