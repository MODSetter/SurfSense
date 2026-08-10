"""Restore a generated artifact's source into the current sandbox."""

from __future__ import annotations

from pathlib import PurePosixPath

from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool, tool
from sqlalchemy import select

from app.config import config as app_config
from app.db import Document, shielded_async_session
from app.file_storage.factory import get_storage_backend
from app.file_storage.persistence.enums import DocumentFileKind
from app.file_storage.persistence.models import DocumentFile
from app.sandbox import get_registry

from .thread_resolver import resolve_root_thread_id


def create_load_artifact_source_tool(
    *, workspace_id: int, thread_id: int | None = None
) -> BaseTool:
    """Build the source-restoration tool with workspace dependencies injected."""

    @tool
    async def load_artifact_source(
        document_id: int,
        runtime: ToolRuntime,
    ) -> str:
        """Load a generated artifact's current source into the sandbox.

        Use the document_id from the artifact roster before revising an existing
        artifact. Edit the returned path, regenerate and verify the deliverable,
        then pass both paths and the same document_id to save_artifact.
        """
        async with shielded_async_session() as db_session:
            document = await db_session.scalar(
                select(Document).where(
                    Document.id == document_id,
                    Document.workspace_id == workspace_id,
                )
            )
            if document is None or not (document.document_metadata or {}).get(
                "generated"
            ):
                raise ValueError("artifact does not exist in this workspace")

            source = await db_session.scalar(
                select(DocumentFile).where(
                    DocumentFile.document_id == document_id,
                    DocumentFile.workspace_id == workspace_id,
                    DocumentFile.kind == DocumentFileKind.GENERATED,
                    DocumentFile.role == "source",
                )
            )
            if source is None:
                raise ValueError("artifact has no stored source")

        if source.size_bytes > app_config.ARTIFACT_MAX_FILE_BYTES:
            raise ValueError(
                f"Artifact source is {source.size_bytes} bytes; limit is "
                f"{app_config.ARTIFACT_MAX_FILE_BYTES} bytes"
            )

        data = bytearray()
        async for chunk in get_storage_backend().open_stream(source.storage_key):
            data.extend(chunk)
            if len(data) > app_config.ARTIFACT_MAX_FILE_BYTES:
                raise ValueError("artifact source exceeds the configured size limit")

        filename = PurePosixPath(source.original_filename).name
        if not filename:
            raise ValueError("artifact source has an invalid filename")
        sandbox_path = f"/workspace/artifact-{document_id}-{filename}"
        root_thread_id = resolve_root_thread_id(runtime, thread_id)
        sandbox = await (await get_registry()).get_session(
            root_thread_id, workspace_id
        )
        await sandbox.write_file(sandbox_path, bytes(data))
        return sandbox_path

    return load_artifact_source
