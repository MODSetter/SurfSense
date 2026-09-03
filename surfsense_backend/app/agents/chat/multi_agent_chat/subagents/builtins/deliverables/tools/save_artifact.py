"""Persist Markdown or sandbox-generated files as first-class artifacts."""

from __future__ import annotations

import json
import logging
import shlex
from dataclasses import asdict
from pathlib import PurePosixPath

from langchain.tools import ToolRuntime
from langchain_core.tools import tool

from app.agents.chat.multi_agent_chat.shared.receipts.command import with_receipt
from app.agents.chat.multi_agent_chat.shared.receipts.receipt import make_receipt
from app.artifacts import ArtifactFileInput, ArtifactFileStreamInput, save_artifact
from app.artifacts.infographic.selection import generation_sidecar_path
from app.artifacts.service import ArtifactInputFile
from app.artifacts.verification.formats.base import FormatAdapter
from app.artifacts.verification.formats.registry import (
    get_format_adapter,
    validate_format_path,
)
from app.artifacts.verification.receipt import (
    artifact_path_lock,
    read_receipt,
    receipt_path,
    sha256_bytes,
)
from app.capabilities.core import ActivityDescriptor
from app.config import config as app_config
from app.db import shielded_async_session
from app.sandbox import SandboxSession, get_registry

from .thread_resolver import resolve_root_thread_id

logger = logging.getLogger(__name__)


def _required_markdown(value: str | None) -> str:
    if value is None or not value.strip():
        raise ValueError("markdown_representation must not be empty")
    return value


async def _read_artifact_file(
    session: SandboxSession, path: str, role: str, adapter: FormatAdapter
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

    validate_format_path(adapter, path)
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


async def _consume_verification(
    session: SandboxSession, primary_path: str, preview_path: str | None
) -> None:
    paths = [receipt_path(primary_path)]
    if preview_path:
        paths.append(preview_path)
    try:
        # Invalidate first so a failed best-effort unlink cannot replay the receipt.
        await session.write_file(receipt_path(primary_path), b"")
        result = await session.run_command(
            f"rm -f -- {' '.join(shlex.quote(path) for path in paths)}"
        )
        if not result.ok:
            logger.warning("Could not clean consumed artifact verification state")
    except Exception:
        logger.warning(
            "Could not clean consumed artifact verification state", exc_info=True
        )


async def _cleanup_video_workdir(session: SandboxSession, primary_path: str) -> None:
    """Best-effort cleanup after the streamed MP4 is durably committed."""
    sidecar_path = f"{primary_path}.segments.json"
    try:
        metadata = json.loads((await session.read_file(sidecar_path)).decode())
        workdir = PurePosixPath(metadata["render_workdir"])
        workspace = PurePosixPath("/workspace")
        if (
            workdir == workspace
            or not workdir.is_absolute()
            or not workdir.is_relative_to(workspace)
        ):
            raise ValueError("Invalid video render workdir")
        result = await session.run_command(
            f"rm -rf -- {shlex.quote(str(workdir))} "
            f"{shlex.quote(sidecar_path)} {shlex.quote(primary_path)}"
        )
        if not result.ok:
            raise RuntimeError("Sandbox cleanup command failed")
    except (FileNotFoundError, KeyError, UnicodeDecodeError, ValueError):
        logger.warning("Could not resolve video render workdir for cleanup")
    except Exception:
        logger.warning("Could not clean video render workdir", exc_info=True)


async def _cleanup_infographic_staging(
    session: SandboxSession,
    primary_path: str,
) -> None:
    markdown_path = str(PurePosixPath(primary_path).with_suffix(".md"))
    sidecar_path = generation_sidecar_path(primary_path)
    result = await session.run_command(
        "rm -f -- "
        + " ".join(
            shlex.quote(path)
            for path in (primary_path, markdown_path, sidecar_path)
        )
    )
    if not result.ok:
        logger.warning("Could not clean infographic staging files")


def _public_error(exc: Exception) -> str:
    if isinstance(exc, FileNotFoundError):
        return (
            "The artifact file is missing. Generate it again, then verify and save it."
        )
    if isinstance(exc, PermissionError):
        return "The artifact file could not be accessed in the sandbox."
    if isinstance(exc, TimeoutError):
        return "The sandbox timed out while saving the artifact. Please try again."
    if isinstance(exc, ValueError):
        if "verification receipt" in str(exc).lower():
            return "Verify this file again before presenting it"
        return str(exc)
    return "The artifact could not be saved. Please try again."


def create_save_artifact_tool(workspace_id: int):
    """Create the artifact tool with workspace dependencies injected."""

    @tool
    async def save_artifact_tool(
        title: str,
        runtime: ToolRuntime,
        markdown_representation: str | None = None,
        path: str | None = None,
        artifact_id: int | None = None,
        expected_generation: int | None = None,
        description: str | None = None,
    ):
        """Save a durable deliverable, or revise an existing generated artifact.

        For Markdown-only work, omit path and pass markdown_representation.
        Generated files must first pass verify_artifact for the exact output
        bytes at path; the backend owns any preview. To revise an artifact, use
        the artifact_id and expected_generation returned by
        load_artifact_for_revision. Changing the title, filename, or design does
        not make a new artifact. Omit artifact_id only for a genuinely new
        deliverable or an explicitly requested separate copy.
        """
        del description
        root_thread_id = resolve_root_thread_id(runtime)
        try:
            files: list[ArtifactInputFile] = []
            extra_metadata = None
            if path is not None:
                session = await (await get_registry()).get_session(
                    root_thread_id, workspace_id
                )
                lock = artifact_path_lock(session.session_id, path)
                async with lock:
                    verification = await read_receipt(
                        session,
                        app_config.SECRET_KEY,
                        workspace_id=workspace_id,
                        primary_path=path,
                    )
                    primary_adapter = get_format_adapter(verification.format)
                    validate_format_path(primary_adapter, path)
                    if primary_adapter.markdown_projection is None:
                        markdown_representation = _required_markdown(
                            markdown_representation
                        )
                    if verification.primary_path != path:
                        raise ValueError(
                            "The artifact changed after verification. Verify it "
                            "again, then save."
                        )
                    if primary_adapter.requires_markdown_binding:
                        expected_markdown_hash = (
                            verification.markdown_representation_sha256
                        )
                        if expected_markdown_hash is None:
                            raise ValueError(
                                "The verification receipt does not bind the "
                                f"{primary_adapter.name} Markdown"
                            )
                        if expected_markdown_hash != sha256_bytes(
                            markdown_representation.encode("utf-8")
                        ):
                            raise ValueError(
                                f"The {primary_adapter.name} Markdown changed after "
                                "verification. "
                                "Verify both files again, then save."
                            )
                    primary: ArtifactInputFile
                    if primary_adapter.name == "video":
                        filename = PurePosixPath(path).name
                        if not filename:
                            raise ValueError(f"Artifact path must name a file: {path}")
                        primary = ArtifactFileStreamInput(
                            chunks=session.read_file_stream(path),
                            filename=filename,
                            mime_type=primary_adapter.mime_type,
                            expected_sha256=verification.primary_sha256,
                        )
                    else:
                        primary = await _read_artifact_file(
                            session, path, "primary", primary_adapter
                        )
                        if verification.primary_sha256 != sha256_bytes(primary.data):
                            raise ValueError(
                                "The artifact changed after verification. Verify it "
                                "again, then save."
                            )
                        if primary_adapter.markdown_projection is not None:
                            projected_markdown = primary_adapter.markdown_projection(
                                primary.data
                            )
                            if (
                                markdown_representation is not None
                                and markdown_representation != projected_markdown
                            ):
                                raise ValueError(
                                    "markdown_representation is derived from the "
                                    "verified artifact and cannot be overridden"
                                )
                            markdown_representation = projected_markdown
                    preview = (
                        await _read_artifact_file(
                            session,
                            verification.preview_path,
                            "preview",
                            get_format_adapter("pdf"),
                        )
                        if verification.preview_path is not None
                        else None
                    )
                    if preview is not None and (
                        verification.preview_sha256 != sha256_bytes(preview.data)
                    ):
                        raise ValueError(
                            "The preview changed after verification. Verify the "
                            "artifact again, then save."
                        )
                    extra_metadata = {
                        "verification": {
                            "verified": verification.visual != "unavailable",
                            "reason": verification.unavailable_reason,
                        },
                        **(
                            {"generation": verification.provenance}
                            if verification.provenance is not None
                            else {}
                        ),
                    }
                    files.append(primary)
                    if preview is not None:
                        files.append(preview)
                    async with shielded_async_session() as db_session:
                        saved = await save_artifact(
                            db_session,
                            workspace_id=workspace_id,
                            thread_id=root_thread_id,
                            tool_call_id=runtime.tool_call_id,
                            title=title,
                            markdown_representation=markdown_representation,
                            files=files,
                            artifact_id=artifact_id,
                            expected_generation=expected_generation,
                            extra_metadata=extra_metadata,
                            format=verification.format,
                            committed_by_turn=True,
                        )
                    await _consume_verification(
                        session, path, verification.preview_path
                    )
                    if primary_adapter.name == "video":
                        await _cleanup_video_workdir(session, path)
                    elif primary_adapter.name == "infographic":
                        await _cleanup_infographic_staging(session, path)
            else:
                markdown_representation = _required_markdown(markdown_representation)
                async with shielded_async_session() as db_session:
                    saved = await save_artifact(
                        db_session,
                        workspace_id=workspace_id,
                        thread_id=root_thread_id,
                        tool_call_id=runtime.tool_call_id,
                        title=title,
                        markdown_representation=markdown_representation,
                        files=files,
                        artifact_id=artifact_id,
                        expected_generation=expected_generation,
                        extra_metadata=extra_metadata,
                        committed_by_turn=True,
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
            error = _public_error(exc)
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
    save_artifact_tool.metadata = {
        "activity_descriptor": ActivityDescriptor(
            active_title="Preparing the file",
            completed_title="Presented file",
            category="artifact",
            icon_key="file-output",
            kind="save_artifact",
        ).as_metadata()
    }
    return save_artifact_tool
