"""Persist Markdown or sandbox-generated files as first-class artifacts."""

from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import PurePosixPath

from langchain.tools import ToolRuntime
from langchain_core.tools import tool

from app.agents.chat.multi_agent_chat.shared.receipts.command import with_receipt
from app.agents.chat.multi_agent_chat.shared.receipts.receipt import make_receipt
from app.artifacts import ArtifactFileInput, save_artifact
from app.artifacts.source_formats import validate_source_file
from app.artifacts.verification.formats.registry import get_format_adapter
from app.artifacts.verification.receipt import read_receipt, sha256_bytes
from app.config import config as app_config
from app.db import shielded_async_session
from app.sandbox import SandboxSession, get_registry

from .thread_resolver import resolve_root_thread_id

logger = logging.getLogger(__name__)


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

    if role == "source":
        mime_type = validate_source_file(path, data)
    else:
        adapter = get_format_adapter(path)
        if role == "preview" and adapter.name != "pdf":
            raise ValueError("Artifact previews must be PDF files")
        if role not in {"primary", "preview"}:
            raise ValueError(f"Unsupported artifact file role: {role}")
        mime_type = adapter.mime_type
    return ArtifactFileInput(
        data=data,
        filename=filename,
        mime_type=mime_type,
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
        artifact_id: int | None = None,
        expected_generation: int | None = None,
        description: str | None = None,
    ):
        """Save a durable deliverable, or revise an existing generated artifact.

        For Markdown-only work, omit path and pass markdown_representation.
        For generated files, pass both the deliverable path and the source_path
        that produced it, plus an accessible Markdown representation for search.
        preview_path is an optional rendered preview. To revise an artifact, use
        the artifact_id and expected_generation returned by load_artifact_source,
        edit and re-render the stored source, then save with both values. Changing
        the title, filename, or design does not make a new artifact. Omit
        artifact_id only for a genuinely new deliverable or an explicitly
        requested separate copy.
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
                primary = await _read_artifact_file(session, path, "primary")
                source = await _read_artifact_file(session, source_path, "source")
                preview = (
                    await _read_artifact_file(session, preview_path, "preview")
                    if preview_path is not None
                    else None
                )
                verification = await read_receipt(
                    session,
                    app_config.SECRET_KEY,
                    workspace_id=workspace_id,
                )
                primary_adapter = get_format_adapter(path)
                if verification.format != primary_adapter.name:
                    raise ValueError(
                        "The verification receipt names another artifact format"
                    )
                if verification.primary_path != path or (
                    verification.primary_sha256 != sha256_bytes(primary.data)
                ):
                    raise ValueError(
                        "The artifact changed after verification. Verify it again, "
                        "then save."
                    )
                if verification.preview_path != preview_path:
                    raise ValueError(
                        "The preview does not match the verified artifact. Verify the "
                        "artifact again and save the returned preview."
                    )
                if preview is not None and (
                    verification.preview_sha256 != sha256_bytes(preview.data)
                ):
                    raise ValueError(
                        "The preview changed after verification. Verify the artifact "
                        "again, then save."
                    )
                extra_metadata = {
                    "verification": {
                        "verified": verification.visual != "unavailable",
                        "reason": verification.unavailable_reason,
                    }
                }
                files.extend((primary, source))
                if preview is not None:
                    files.append(preview)
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
                    artifact_id=artifact_id,
                    expected_generation=expected_generation,
                    extra_metadata=extra_metadata,
                )
            return with_receipt(
                payload=asdict(saved),
                receipt=make_receipt(
                    route="deliverables",
                    type="artifact",
                    operation="generate",
                    status="success",
                    external_id=str(saved.artifact_id),
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
