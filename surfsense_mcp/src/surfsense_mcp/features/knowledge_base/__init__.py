"""Knowledge-base tools: search the KB and manage its documents.

Semantic search plus the document lifecycle — list, read, add text, upload a
file, update, and delete — over a workspace's knowledge base. Search and reads
default to the active workspace; document ids identify a single document across
the whole account, so id-addressed tools need no workspace.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from ...core.client import SurfSenseClient
from ...core.errors import ToolError
from ...core.rendering import ResponseFormatParam, clip, to_json
from ...core.workspace_context import WorkspaceContext, WorkspaceParam
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

_DOCUMENT_ID = Annotated[
    int,
    Field(
        description="Document id from surfsense_search_knowledge_base or "
        "surfsense_list_documents results."
    ),
]

_DOCUMENT_TYPES = Annotated[
    list[str] | None,
    Field(
        description="Restrict to these document types, e.g. "
        "['FILE', 'CRAWLED_URL', 'YOUTUBE_VIDEO']. Omit for all types."
    ),
]


def register(
    mcp: FastMCP, client: SurfSenseClient, context: WorkspaceContext
) -> None:
    """Register the knowledge-base tools on the server."""

    @mcp.tool(
        name="surfsense_search_knowledge_base",
        title="Search knowledge base",
        annotations=_READ,
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
        document_types: _DOCUMENT_TYPES = None,
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
        annotations=_READ,
        structured_output=False,
    )
    async def list_documents(
        document_types: _DOCUMENT_TYPES = None,
        folder_id: Annotated[
            int | None,
            Field(description="Only documents in this folder. Omit for all."),
        ] = None,
        page: Annotated[
            int, Field(ge=0, description="Zero-based page number.")
        ] = 0,
        page_size: Annotated[
            int, Field(ge=1, description="Documents per page.")
        ] = 20,
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
        annotations=_READ,
        structured_output=False,
    )
    async def get_document(
        document_id: _DOCUMENT_ID,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Read one document's full content and metadata by id.

        Use this after surfsense_search_knowledge_base or
        surfsense_list_documents to open a specific document — search results
        only include the matching passages, this returns the whole text.
        """
        document = await client.request("GET", f"/documents/{document_id}")
        if response_format == "json":
            return clip(to_json(document))
        return _render_document(document)

    @mcp.tool(
        name="surfsense_add_document",
        title="Add a note",
        annotations=_WRITE,
        structured_output=False,
    )
    async def add_document(
        title: Annotated[
            str,
            Field(min_length=1, description="Short descriptive title for the note."),
        ],
        content: Annotated[
            str,
            Field(
                min_length=1,
                description="The note's body; plain text or markdown.",
            ),
        ],
        source_url: Annotated[
            str | None,
            Field(description="Where the text came from, if anywhere."),
        ] = None,
        workspace: WorkspaceParam = None,
    ) -> str:
        """Save a text or markdown note into the workspace's knowledge base.

        Use this to store notes, summaries, or findings so they become
        searchable later — e.g. after finishing a piece of research. For files
        on disk use surfsense_upload_file instead. Indexing is asynchronous,
        so the note may take a moment to appear in search.
        Example: title='NotebookLM subreddits', content='- r/notebooklm ...'.
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
        name="surfsense_upload_file",
        title="Upload a file",
        annotations=_WRITE,
        structured_output=False,
    )
    async def upload_file(
        file_path: Annotated[
            str,
            Field(
                description="Path to a local file, e.g. "
                "'C:/Users/me/report.pdf' or '~/notes/summary.md'."
            ),
        ],
        use_vision_llm: Annotated[
            bool,
            Field(
                description="True reads scanned or image-heavy files with a "
                "vision model (slower)."
            ),
        ] = False,
        workspace: WorkspaceParam = None,
    ) -> str:
        """Upload a local file (PDF, docx, markdown, etc.) into the knowledge base.

        Use this to ingest a file from disk so its content becomes searchable;
        for text you already have in hand use surfsense_add_document instead.
        The file is parsed, chunked, and indexed asynchronously. Duplicate
        files are detected and skipped.
        Example: file_path='C:/Users/me/report.pdf'.
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
        name="surfsense_update_document",
        title="Replace a document's content",
        annotations=_WRITE,
        structured_output=False,
    )
    async def update_document(
        document_id: _DOCUMENT_ID,
        content: Annotated[
            str,
            Field(
                min_length=1,
                description="New full text; replaces the existing content "
                "entirely.",
            ),
        ],
    ) -> str:
        """Replace a document's stored content by id.

        Use this to correct or rewrite a document's text. The new content
        REPLACES the old entirely — to append, read the document first with
        surfsense_get_document and resend the combined text. Search chunks are
        not re-indexed by this call.
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
        name="surfsense_delete_document",
        title="Delete a document",
        annotations=_DELETE,
        structured_output=False,
    )
    async def delete_document(document_id: _DOCUMENT_ID) -> str:
        """Permanently delete a document from the knowledge base by id.

        Use this only when the user explicitly asks to remove a document —
        deletion cannot be undone. The document stops appearing in searches
        immediately.
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
