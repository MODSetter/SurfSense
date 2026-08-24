"""Copy a workspace document's original upload into the sandbox."""

from __future__ import annotations

import shlex
from pathlib import PurePosixPath

from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool, tool

from app.capabilities.core import ActivityDescriptor
from app.config import config as app_config
from app.db import shielded_async_session
from app.file_storage.persistence.enums import DocumentFileKind
from app.file_storage.service import get_document_file, open_document_file_stream
from app.knowledge_store.paths import virtual_path_to_doc
from app.sandbox import get_registry

from .thread_resolver import resolve_root_thread_id

_NO_BINARY = (
    "'{path}' has no stored upload to convert — it is authored content, not an "
    "uploaded file. Ask the knowledge_base subagent to read it, then generate "
    "the deliverable from that text."
)


async def _read_original(record) -> bytes:
    if record.size_bytes > app_config.ARTIFACT_MAX_FILE_BYTES:
        raise ValueError(
            f"Source document is {record.size_bytes} bytes; limit is "
            f"{app_config.ARTIFACT_MAX_FILE_BYTES} bytes"
        )
    data = bytearray()
    async for chunk in open_document_file_stream(record):
        data.extend(chunk)
        if len(data) > app_config.ARTIFACT_MAX_FILE_BYTES:
            raise ValueError("source document exceeds the configured size limit")
    return bytes(data)


def create_load_source_document_tool(*, workspace_id: int) -> BaseTool:
    """Build the knowledge-base-to-sandbox loader."""

    @tool
    async def load_source_document(
        path: str,
        runtime: ToolRuntime,
    ) -> dict[str, str | int]:
        """Copy a workspace document's original uploaded file into the sandbox.

        Use this to convert, reformat, or extract from a file the user already
        has, given its `/documents/...` path. Those paths are knowledge-base
        handles and do not exist on the sandbox filesystem, so read them with
        this tool rather than opening them directly. Returns the real sandbox
        path to work from.
        """
        async with shielded_async_session() as db_session:
            document = await virtual_path_to_doc(
                db_session, workspace_id=workspace_id, virtual_path=path
            )
            if document is None:
                raise ValueError(f"No document exists at '{path}' in this workspace")
            record = await get_document_file(
                db_session,
                document_id=document.id,
                kind=DocumentFileKind.ORIGINAL,
            )
            if record is None:
                raise ValueError(_NO_BINARY.format(path=path))
            document_id = document.id
            filename = PurePosixPath(record.original_filename).name
            mime_type = record.mime_type or "application/octet-stream"
            data = await _read_original(record)

        # The upload's name is user-controlled, so only its extension is
        # carried into the sandbox path; the real name goes back as metadata.
        suffix = PurePosixPath(filename).suffix.lower()
        working_dir = f"/workspace/sources/{document_id}"
        source_path = f"{working_dir}/source{suffix}"

        sandbox = await (await get_registry()).get_session(
            resolve_root_thread_id(runtime), workspace_id
        )
        created = await sandbox.run_command(f"mkdir -p -- {shlex.quote(working_dir)}")
        if not created.ok:
            raise RuntimeError("Could not create the source document workspace")
        await sandbox.write_file(source_path, data)

        return {
            "source_path": source_path,
            "filename": filename,
            "mime_type": mime_type,
            "size_bytes": len(data),
        }

    load_source_document.metadata = {
        "activity_descriptor": ActivityDescriptor(
            active_title="Opening the source file",
            completed_title="Opened the source file",
            category="artifact",
            icon_key="file-input",
            kind="load_source_document",
            lifecycle="phase",
        ).as_metadata()
    }
    return load_source_document
