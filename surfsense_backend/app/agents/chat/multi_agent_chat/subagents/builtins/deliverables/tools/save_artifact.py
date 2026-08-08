"""Persist Markdown or sandbox-generated files as first-class artifacts."""

from __future__ import annotations

import logging
import mimetypes
from dataclasses import asdict
from pathlib import PurePosixPath

import magic
from langchain.tools import ToolRuntime
from langchain_core.tools import tool

from app.agents.chat.multi_agent_chat.shared.receipts.command import with_receipt
from app.agents.chat.multi_agent_chat.shared.receipts.receipt import make_receipt
from app.artifacts import ArtifactFileInput, save_artifact
from app.config import config as app_config
from app.db import shielded_async_session
from app.sandbox import SandboxSession, get_registry

from .thread_resolver import resolve_root_thread_id

logger = logging.getLogger(__name__)


def _mime_types_compatible(extension_mime: str, sniffed_mime: str) -> bool:
    if extension_mime == sniffed_mime or sniffed_mime == "application/octet-stream":
        return True
    if extension_mime.startswith("text/") and sniffed_mime.startswith("text/"):
        return True
    return (
        extension_mime.startswith(
            "application/vnd.openxmlformats-officedocument."
        )
        and sniffed_mime in {"application/zip", "application/x-zip"}
    )


async def _read_artifact_file(
    session: SandboxSession, path: str, role: str
) -> ArtifactFileInput:
    filename = PurePosixPath(path).name
    if not filename:
        raise ValueError(f"Artifact path must name a file: {path}")
    data = await session.read_file(path)
    if not data:
        raise ValueError(f"Artifact file is empty: {path}")
    if len(data) > app_config.ARTIFACT_MAX_FILE_BYTES:
        raise ValueError(
            f"Artifact file {filename} is {len(data)} bytes; limit is "
            f"{app_config.ARTIFACT_MAX_FILE_BYTES} bytes"
        )

    extension_mime = mimetypes.guess_type(filename)[0]
    sniffed_mime = magic.from_buffer(data, mime=True)
    if extension_mime and sniffed_mime and not _mime_types_compatible(
        extension_mime, sniffed_mime
    ):
        raise ValueError(
            f"File contents ({sniffed_mime}) do not match {filename} "
            f"({extension_mime})"
        )
    return ArtifactFileInput(
        data=data,
        filename=filename,
        mime_type=extension_mime or sniffed_mime or "application/octet-stream",
        role=role,
    )


def create_save_artifact_tool(workspace_id: int, thread_id: int | None = None):
    """Create the artifact tool with workspace dependencies injected."""

    @tool
    async def save_artifact_tool(
        title: str,
        runtime: ToolRuntime,
        markdown_representation: str | None = None,
        path: str | None = None,
        preview_path: str | None = None,
        document_id: int | None = None,
        content: str | None = None,
        description: str | None = None,
    ):
        """Save a durable deliverable, or revise an existing generated artifact.

        For Markdown-only work, omit path and pass markdown_representation.
        For generated files, pass their sandbox path and an accessible Markdown
        representation for search. preview_path is an optional rendered preview.
        Pass document_id only when revising that artifact. ``content`` remains a
        backwards-compatible alias for Markdown-only callers.
        """
        del description
        root_thread_id = resolve_root_thread_id(runtime, thread_id)
        try:
            markdown = markdown_representation or content
            if not markdown or not markdown.strip():
                raise ValueError("markdown_representation must not be empty")
            files: list[ArtifactFileInput] = []
            if path is not None:
                session = await (await get_registry()).get_session(
                    root_thread_id, workspace_id
                )
                files.append(await _read_artifact_file(session, path, "primary"))
                if preview_path is not None:
                    files.append(
                        await _read_artifact_file(session, preview_path, "preview")
                    )
            elif preview_path is not None:
                raise ValueError("preview_path requires a primary path")

            async with shielded_async_session() as session:
                saved = await save_artifact(
                    session,
                    workspace_id=workspace_id,
                    thread_id=root_thread_id,
                    tool_call_id=runtime.tool_call_id,
                    title=title,
                    markdown_representation=markdown,
                    files=files,
                    document_id=document_id,
                )
            return with_receipt(
                payload=asdict(saved),
                receipt=make_receipt(
                    route="deliverables",
                    type="artifact",
                    operation="generate",
                    status="success",
                    external_id=str(saved.document_id),
                    preview=saved.title,
                ),
                tool_call_id=runtime.tool_call_id,
            )
        except Exception as exc:
            error = str(exc)
            logger.exception("[save_artifact] %s", error)
            return with_receipt(
                payload={"status": "failed", "error": error},
                receipt=make_receipt(
                    route="deliverables",
                    type="artifact",
                    operation="generate",
                    status="failed",
                    error=error,
                ),
                tool_call_id=runtime.tool_call_id,
            )

    # Keep the public tool name frozen even though the Python symbol avoids
    # shadowing the service imported above.
    save_artifact_tool.name = "save_artifact"
    return save_artifact_tool
