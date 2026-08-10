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
from .verification import check_verification

logger = logging.getLogger(__name__)


def _mime_types_compatible(extension_mime: str, sniffed_mime: str) -> bool:
    if extension_mime == sniffed_mime or sniffed_mime == "application/octet-stream":
        return True
    if extension_mime.startswith("text/") and sniffed_mime.startswith("text/"):
        return True
    if extension_mime == "application/javascript" and sniffed_mime.startswith("text/"):
        return True
    return extension_mime.startswith(
        "application/vnd.openxmlformats-officedocument."
    ) and sniffed_mime in {"application/zip", "application/x-zip"}


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
    if (
        extension_mime
        and sniffed_mime
        and not _mime_types_compatible(extension_mime, sniffed_mime)
    ):
        raise ValueError(
            f"File contents ({sniffed_mime}) do not match {filename} ({extension_mime})"
        )
    return ArtifactFileInput(
        data=data,
        filename=filename,
        mime_type=extension_mime or sniffed_mime or "application/octet-stream",
        role=role,
    )


def create_save_artifact_tool(workspace_id: int):
    """Create the artifact tool with workspace dependencies injected."""

    @tool
    async def save_artifact_tool(
        title: str,
        runtime: ToolRuntime,
        markdown_representation: str | None = None,
        path: str | None = None,
        source_path: str | None = None,
        preview_path: str | None = None,
        document_id: int | None = None,
        description: str | None = None,
    ):
        """Save a durable deliverable, or revise an existing generated artifact.

        For Markdown-only work, omit path and pass markdown_representation.
        For generated files, pass both the deliverable path and the source_path
        that produced it, plus an accessible Markdown representation for search.
        preview_path is an optional rendered preview. To revise an artifact, use
        the document_id from the artifact roster, load its stored source first,
        edit and re-render it, then save with that same document_id. When the user
        is not clearly referring to an existing artifact, create a new one.
        """
        del description
        root_thread_id = resolve_root_thread_id(runtime)
        try:
            if not markdown_representation or not markdown_representation.strip():
                raise ValueError("markdown_representation must not be empty")
            files: list[ArtifactFileInput] = []
            extra_metadata = None
            if path is not None:
                if source_path is None:
                    raise ValueError("source_path is required for generated files")
                session = await (await get_registry()).get_session(
                    root_thread_id, workspace_id
                )
                verification = await check_verification(session, path)
                if not verification.verified and verification.reason is None:
                    raise ValueError(
                        "Artifact changed after its last verification. Run the "
                        "format's structural and visual verification steps again "
                        "before saving."
                    )
                extra_metadata = {
                    "verification": {
                        "verified": verification.verified,
                        "reason": verification.reason,
                    }
                }
                files.append(await _read_artifact_file(session, path, "primary"))
                files.append(await _read_artifact_file(session, source_path, "source"))
                if preview_path is not None:
                    files.append(
                        await _read_artifact_file(session, preview_path, "preview")
                    )
            elif source_path is not None or preview_path is not None:
                raise ValueError("source_path and preview_path require a primary path")

            async with shielded_async_session() as session:
                saved = await save_artifact(
                    session,
                    workspace_id=workspace_id,
                    thread_id=root_thread_id,
                    tool_call_id=runtime.tool_call_id,
                    title=title,
                    markdown_representation=markdown_representation,
                    files=files,
                    document_id=document_id,
                    extra_metadata=extra_metadata,
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
