"""Restore a generated artifact's source into the current sandbox."""

from __future__ import annotations

from pathlib import PurePosixPath

from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool, tool
from sqlalchemy import select

from app.artifacts.persistence import Artifact, ArtifactFile, ArtifactFileRole
from app.config import config as app_config
from app.db import shielded_async_session
from app.file_storage.factory import get_storage_backend
from app.sandbox import get_registry

from .thread_resolver import resolve_root_thread_id


def create_load_artifact_source_tool(*, workspace_id: int) -> BaseTool:
    """Build the source-restoration tool with workspace dependencies injected."""

    @tool
    async def load_artifact_source(
        artifact_id: int,
        runtime: ToolRuntime,
    ) -> dict[str, str | int]:
        """Load a generated artifact's current source into the sandbox.

        Use the artifact_id from the artifact roster before revising an existing
        artifact. The result binds the restored source_path to the artifact_id
        that must be passed to save_artifact after editing, regeneration, and
        verification.
        """
        async with shielded_async_session() as db_session:
            artifact = await db_session.scalar(
                select(Artifact).where(
                    Artifact.id == artifact_id,
                    Artifact.workspace_id == workspace_id,
                )
            )
            if artifact is None:
                raise ValueError("artifact does not exist in this workspace")

            source = await db_session.scalar(
                select(ArtifactFile).where(
                    ArtifactFile.artifact_id == artifact_id,
                    ArtifactFile.role == ArtifactFileRole.SOURCE,
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
        backend = get_storage_backend(source.storage_backend)
        async for chunk in backend.open_stream(source.storage_key):
            data.extend(chunk)
            if len(data) > app_config.ARTIFACT_MAX_FILE_BYTES:
                raise ValueError("artifact source exceeds the configured size limit")

        filename = PurePosixPath(source.original_filename).name
        if not filename:
            raise ValueError("artifact source has an invalid filename")
        sandbox_path = f"/workspace/artifact-{artifact_id}-{filename}"
        root_thread_id = resolve_root_thread_id(runtime)
        sandbox = await (await get_registry()).get_session(root_thread_id, workspace_id)
        await sandbox.write_file(sandbox_path, bytes(data))
        return {
            "source_path": sandbox_path,
            "artifact_id": artifact_id,
            "expected_version": artifact.version,
            "save_instruction": (
                f"Pass artifact_id={artifact_id} and "
                f"expected_version={artifact.version} to save_artifact so "
                "this revision replaces the existing artifact."
            ),
        }

    return load_artifact_source
