"""Knowledge-base write tools: add a note, upload a file, update, and delete.

Add and upload target the active workspace; update and delete address a document
by its account-unique id, so they need no workspace.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ...core.client import SurfSenseClient
from ...core.errors import ToolError
from ...core.workspace_context import WorkspaceContext, WorkspaceParam
from .annotations import DELETE, WRITE, DocumentId
from .note_ingestion import build_note_document


def register(
    mcp: FastMCP, client: SurfSenseClient, context: WorkspaceContext
) -> None:
    """Register the knowledge-base write and delete tools."""

    @mcp.tool(
        name="surfsense_add_document",
        title="Add a note",
        annotations=WRITE,
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
        annotations=WRITE,
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
        annotations=WRITE,
        structured_output=False,
    )
    async def update_document(
        document_id: DocumentId,
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
        annotations=DELETE,
        structured_output=False,
    )
    async def delete_document(document_id: DocumentId) -> str:
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
