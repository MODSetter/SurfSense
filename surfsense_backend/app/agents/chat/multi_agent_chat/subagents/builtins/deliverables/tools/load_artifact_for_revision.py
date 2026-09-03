"""Restore an artifact's current deliverable and Markdown into the sandbox."""

from __future__ import annotations

import shlex
from pathlib import PurePosixPath
from uuid import uuid4

from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool, tool
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.agents.chat.multi_agent_chat.subagents.shared.hitl.questions import (
    StructuredQuestion,
    StructuredQuestionInterrupt,
    StructuredQuestionOption,
    StructuredQuestionOrigin,
    StructuredQuestionRespond,
    is_cancelled,
    request_structured_questions,
    selected_option_id,
)
from app.artifacts.infographic.presets import (
    AUTO_STYLE_ID,
    QUESTION_PRESET_ID,
    QUESTION_PRESET_VERSION,
    VISUAL_STYLE_PRESETS,
    get_visual_style,
    resolve_visual_style,
)
from app.artifacts.infographic.schemas import ResolvedVisualStyle
from app.artifacts.infographic.selection import issue_selection_token
from app.artifacts.persistence import Artifact, ArtifactFileRole
from app.capabilities.core import ActivityDescriptor
from app.config import config as app_config
from app.db import shielded_async_session
from app.file_storage.factory import get_storage_backend
from app.sandbox import get_registry

from .thread_resolver import resolve_root_thread_id

_REVISION_INSTRUCTIONS = {
    "pptx": (
        "Open primary_path with python-pptx, preserve unaffected package content, "
        "and save the edited deck to expected_output_path."
    ),
    "xlsx": (
        "Open primary_path with openpyxl. For formulas, recalculate a temporary "
        "copy with headless LibreOffice and place the result at expected_output_path."
    ),
    "docx": (
        "Open primary_path with python-docx for supported edits and save to "
        "expected_output_path; stop before lossy changes to unsupported structures."
    ),
    "pdf": (
        "Regenerate expected_output_path from markdown_path and current user "
        "context; do not reconstruct the PDF with vision."
    ),
    "html": (
        "Edit primary_path directly, or regenerate the fragment from markdown_path "
        "and the user's instruction, then write it to expected_output_path. Keep it "
        "a self-contained fragment and do not reconstruct it with vision."
    ),
    "video": (
        "Regenerate the video by re-authoring the deck from markdown_path plus "
        "the user's new instruction, render to expected_output_path, then verify "
        "it. Do not edit current.mp4; it is restored for reference only."
    ),
    "mindmap": (
        "Edit markdown_path, render it to expected_output_path with the mind-map "
        "harness, verify both paths together, and save with the returned artifact "
        "ID and generation. Do not edit or reconstruct the PNG."
    ),
    "infographic": (
        "Regenerate the entire PNG from markdown_path with execute(language="
        '"infographic") and the returned infographic_selection_token. Verify the '
        "PNG and Markdown together, then save with the returned artifact ID and "
        "generation. Do not edit or reconstruct the PNG."
    ),
    "flashcards": (
        "Edit the restored JSON deck without changing its schema version, write "
        "the complete deck to expected_output_path, verify it as flashcards, and "
        "save it with the returned artifact ID and generation. Do not edit the "
        "derived Markdown or reconstruct the deck with vision."
    ),
    "quiz": (
        "Edit the restored JSON quiz without changing schema version one. Preserve "
        "exactly four options and one correct option per question, write the "
        "complete quiz to expected_output_path, verify it as quiz, and save it "
        "with the returned artifact ID and generation. Do not edit the derived "
        "Markdown or reconstruct the quiz with vision."
    ),
    "markdown": "Edit markdown_path directly and save it as a Markdown-only revision.",
}


async def _read_primary(record) -> bytes:
    if record.size_bytes > app_config.ARTIFACT_MAX_FILE_BYTES:
        raise ValueError(
            f"Artifact primary is {record.size_bytes} bytes; limit is "
            f"{app_config.ARTIFACT_MAX_FILE_BYTES} bytes"
        )
    data = bytearray()
    backend = get_storage_backend(record.storage_backend)
    async for chunk in backend.open_stream(record.storage_key):
        data.extend(chunk)
        if len(data) > app_config.ARTIFACT_MAX_FILE_BYTES:
            raise ValueError("artifact primary exceeds the configured size limit")
    return bytes(data)


def _request_revision_style(brief: str) -> ResolvedVisualStyle | None:
    response = request_structured_questions(
        StructuredQuestionInterrupt(
            title="Choose an infographic style",
            message="Select the visual direction for this style revision.",
            origin=StructuredQuestionOrigin(
                kind="preset",
                preset_id=QUESTION_PRESET_ID,
                preset_version=QUESTION_PRESET_VERSION,
            ),
            questions=(
                StructuredQuestion(
                    id="visual-style",
                    prompt="Which visual style should be used?",
                    input_type="single_select",
                    presentation="visual_cards",
                    options=(
                        StructuredQuestionOption(
                            id=AUTO_STYLE_ID,
                            label="Auto",
                            description="Choose a style deterministically from the brief.",
                            preview_asset="infographic-style/auto",
                        ),
                        *(
                            StructuredQuestionOption(
                                id=preset.id,
                                label=preset.label,
                                description=preset.description,
                                preview_asset=preset.preview_asset,
                            )
                            for preset in VISUAL_STYLE_PRESETS
                        ),
                    ),
                ),
            ),
        )
    )
    if is_cancelled(response):
        return None
    if not isinstance(response, StructuredQuestionRespond):
        raise ValueError("Infographic style response is invalid")
    return resolve_visual_style(
        selected_option_id(response, "visual-style"),
        brief,
    )


def create_load_artifact_for_revision_tool(*, workspace_id: int) -> BaseTool:
    """Build the binary-oriented revision loader."""

    @tool
    async def load_artifact_for_revision(
        artifact_id: int,
        runtime: ToolRuntime,
        change_infographic_style: bool = False,
        infographic_brief: str | None = None,
    ) -> dict[str, object]:
        """Load the latest artifact generation into an isolated revision directory.

        Use this before revising an artifact from the roster. Binary artifacts
        restore their current primary plus Markdown context. Markdown artifacts
        restore only their editable context. Save the result with the returned
        artifact_id and expected_generation so the revision updates in place.
        """
        async with shielded_async_session() as db_session:
            artifact = await db_session.scalar(
                select(Artifact)
                .options(
                    selectinload(Artifact.document),
                    selectinload(Artifact.files),
                )
                .where(
                    Artifact.id == artifact_id,
                    Artifact.workspace_id == workspace_id,
                )
            )
            if artifact is None:
                raise ValueError("artifact does not exist in this workspace")
            primary = next(
                (
                    record
                    for record in artifact.files
                    if record.role is ArtifactFileRole.PRIMARY
                ),
                None,
            )
            markdown = (
                artifact.document.source_markdown or artifact.document.content or ""
            )
            generation = artifact.generation
            artifact_format = artifact.format
            artifact_metadata = getattr(artifact, "artifact_metadata", None) or {}

        markdown_data = markdown.encode()
        if len(markdown_data) > app_config.ARTIFACT_MAX_FILE_BYTES:
            raise ValueError("artifact Markdown exceeds the configured size limit")

        root_thread_id = resolve_root_thread_id(runtime)
        infographic_selection_token = None
        style_provenance = None
        if artifact_format == "infographic":
            raw_generation = artifact_metadata.get("generation")
            if not isinstance(raw_generation, dict):
                raise ValueError(
                    "Infographic revision is missing trusted style provenance"
                )
            current_style_id = raw_generation.get("resolved_style_id")
            if not isinstance(current_style_id, str):
                raise ValueError(
                    "Infographic revision is missing its resolved visual style"
                )
            if change_infographic_style:
                resolved = _request_revision_style(infographic_brief or markdown)
                if resolved is None:
                    return {
                        "artifact_id": artifact_id,
                        "format": artifact_format,
                        "status": "cancelled",
                    }
            else:
                current = get_visual_style(current_style_id)
                resolved = ResolvedVisualStyle(
                    requested_id=current.id,
                    preset=current,
                )
            infographic_selection_token = issue_selection_token(
                workspace_id=workspace_id,
                thread_id=root_thread_id,
                preset_id=QUESTION_PRESET_ID,
                preset_version=QUESTION_PRESET_VERSION,
                resolved=resolved,
                secret_key=app_config.SECRET_KEY,
            )
            style_provenance = {
                "question_preset_id": QUESTION_PRESET_ID,
                "question_preset_version": QUESTION_PRESET_VERSION,
                "requested_style_id": resolved.requested_id,
                "resolved_style_id": resolved.resolved_id,
            }

        working_dir = f"/workspace/artifact-revisions/{artifact_id}/{uuid4().hex}"
        markdown_path = f"{working_dir}/context.md"
        sandbox = await (await get_registry()).get_session(
            root_thread_id, workspace_id
        )
        created = await sandbox.run_command(f"mkdir -p -- {shlex.quote(working_dir)}")
        if not created.ok:
            raise RuntimeError("Could not create the artifact revision workspace")
        await sandbox.write_file(markdown_path, markdown_data)

        primary_path: str | None = None
        if primary is not None:
            suffix = PurePosixPath(primary.original_filename).suffix.lower()
            if not suffix:
                raise ValueError("artifact primary filename has no extension")
            primary_path = f"{working_dir}/current{suffix}"
            expected_output_path = f"{working_dir}/revised{suffix}"
            await sandbox.write_file(primary_path, await _read_primary(primary))
        else:
            expected_output_path = markdown_path

        return {
            "artifact_id": artifact_id,
            "format": artifact_format,
            "primary_path": primary_path,
            "markdown_path": markdown_path,
            "expected_output_path": expected_output_path,
            "expected_generation": generation,
            **(
                {
                    "infographic_selection_token": infographic_selection_token,
                    "style_provenance": style_provenance,
                }
                if infographic_selection_token is not None
                else {}
            ),
            "revision_instruction": _REVISION_INSTRUCTIONS.get(
                artifact_format,
                "Edit the restored primary with a format-aware library and save "
                "the result to expected_output_path.",
            ),
            "save_instruction": (
                f"Pass artifact_id={artifact_id} and "
                f"expected_generation={generation} to save_artifact so this "
                "revision replaces the existing artifact."
            ),
        }

    load_artifact_for_revision.metadata = {
        "activity_descriptor": ActivityDescriptor(
            active_title="Opening the artifact",
            completed_title="Opened the artifact",
            category="artifact",
            icon_key="file-input",
            kind="load_artifact_for_revision",
            lifecycle="phase",
        ).as_metadata()
    }
    return load_artifact_for_revision
