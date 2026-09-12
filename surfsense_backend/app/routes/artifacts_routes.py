"""Workspace-scoped artifact manifests, files, downloads, and lifecycle."""

from __future__ import annotations

import io
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.artifacts.flashcards import (
    FlashcardOrderUpdate,
    FlashcardProgressUpdate,
    apply_flashcard_mark,
    apply_flashcard_order,
    reset_flashcard_progress,
    sanitize_flashcard_study_state,
    study_state_digest,
)
from app.artifacts.persistence import (
    Artifact,
    ArtifactFile,
    ArtifactFileRole,
)
from app.artifacts.quiz import (
    QuizAnswerUpdate,
    QuizRetakeUpdate,
    QuizSkipUpdate,
    apply_quiz_answer,
    apply_quiz_retake,
    apply_quiz_skip,
    quiz_state_digest,
    sanitize_quiz_state,
)
from app.artifacts.storage import (
    open_artifact_file_range,
    open_artifact_file_stream,
)
from app.artifacts.verification.formats.flashcards import (
    FlashcardDeckV1,
    parse_flashcards_deck,
)
from app.artifacts.verification.formats.quiz import QuizV1, parse_quiz
from app.auth.context import AuthContext
from app.config import config as app_config
from app.db import Document, Permission, get_async_session
from app.users import get_auth_context
from app.utils.rbac import check_permission

from .document_files_routes import _content_disposition, _is_inline

router = APIRouter()
logger = logging.getLogger(__name__)


def _parse_range(value: str, size: int) -> tuple[int, int]:
    """Parse one byte range, returning inclusive offsets."""
    if size <= 0 or not value.startswith("bytes="):
        raise ValueError("Invalid byte range")
    first = value.removeprefix("bytes=").strip()
    if "," in first:
        raise ValueError("Multiple byte ranges are not supported")
    start_text, separator, end_text = first.partition("-")
    if separator != "-":
        raise ValueError("Invalid byte range")
    if not start_text:
        try:
            suffix_length = int(end_text)
        except ValueError:
            raise ValueError("Invalid byte range") from None
        if suffix_length <= 0:
            raise ValueError("Invalid byte range")
        return max(size - suffix_length, 0), size - 1
    try:
        start = int(start_text)
        end = int(end_text) if end_text else size - 1
    except ValueError:
        raise ValueError("Invalid byte range") from None
    if start < 0 or start >= size or end < start:
        raise ValueError("Unsatisfiable byte range")
    return start, min(end, size - 1)


def _safe_filename_stem(title: str) -> str:
    safe = "".join(
        character if character.isalnum() or character in " -_" else "_"
        for character in title
    ).strip()[:80]
    return safe or "artifact"


def _artifact_filename(title: str, original_filename: str) -> str:
    suffix = Path(original_filename).suffix.lower()
    if not suffix[1:].isalnum() or len(suffix) > 16:
        suffix = ""
    title_without_suffix = (
        title[: -len(suffix)] if suffix and title.lower().endswith(suffix) else title
    )
    return f"{_safe_filename_stem(title_without_suffix)}{suffix}"


def _markdown_filename(title: str) -> str:
    return f"{_safe_filename_stem(title)}.md"


async def _authorize_artifact(
    session: AsyncSession,
    auth: AuthContext,
    workspace_id: int,
    permission: Permission,
    action: str,
) -> None:
    await check_permission(
        session,
        auth,
        workspace_id,
        permission.value,
        f"You don't have permission to {action} artifacts in this workspace",
    )


def _visible_files(artifact: Artifact) -> list[ArtifactFile]:
    return sorted(
        artifact.files,
        key=lambda item: (item.role is not ArtifactFileRole.PRIMARY, item.id),
    )


async def _read_flashcard_deck(artifact: Artifact) -> FlashcardDeckV1:
    primary = next(
        (file for file in artifact.files if file.role is ArtifactFileRole.PRIMARY),
        None,
    )
    if primary is None:
        raise ValueError("Flashcard artifact has no primary file")
    if primary.size_bytes > app_config.ARTIFACT_MAX_FILE_BYTES:
        raise ValueError("Flashcard artifact exceeds the configured size limit")
    data = bytearray()
    async for chunk in open_artifact_file_stream(primary):
        data.extend(chunk)
        if len(data) > app_config.ARTIFACT_MAX_FILE_BYTES:
            raise ValueError("Flashcard artifact exceeds the configured size limit")
    return parse_flashcards_deck(bytes(data))


async def _read_quiz(artifact: Artifact) -> QuizV1:
    primary = next(
        (file for file in artifact.files if file.role is ArtifactFileRole.PRIMARY),
        None,
    )
    if primary is None:
        raise ValueError("Quiz artifact has no primary file")
    if primary.size_bytes > app_config.ARTIFACT_MAX_FILE_BYTES:
        raise ValueError("Quiz artifact exceeds the configured size limit")
    data = bytearray()
    async for chunk in open_artifact_file_stream(primary):
        data.extend(chunk)
        if len(data) > app_config.ARTIFACT_MAX_FILE_BYTES:
            raise ValueError("Quiz artifact exceeds the configured size limit")
    return parse_quiz(bytes(data))


def _file_manifest(
    workspace_id: int, artifact_id: int, record: ArtifactFile
) -> dict[str, object]:
    return {
        "file_id": record.id,
        "role": record.role.value,
        "filename": record.original_filename,
        "mime_type": record.mime_type or "application/octet-stream",
        "size_bytes": record.size_bytes,
        "content_url": (
            f"/api/v1/workspaces/{workspace_id}/artifacts/"
            f"{artifact_id}/files/{record.id}/content"
        ),
    }


def _legacy_ref(artifact: Artifact) -> dict[str, object] | None:
    """Legacy podcast / video / image reference stashed under ``metadata.legacy``."""
    meta = artifact.artifact_metadata or {}
    legacy = meta.get("legacy")
    if not isinstance(legacy, dict):
        return None
    kind = legacy.get("kind")
    legacy_id = legacy.get("id")
    if not isinstance(kind, str) or not isinstance(legacy_id, int):
        return None
    return {"kind": kind, "id": legacy_id}


def _slides_for_remotion(
    workspace_id: int, artifact_id: int, slides: list[object]
) -> list[dict[str, object]]:
    """Public slide payload: artifact-scoped audio URLs, no storage keys."""
    out: list[dict[str, object]] = []
    for raw in slides:
        if not isinstance(raw, dict):
            continue
        slide = dict(raw)
        slide_number = slide.get("slide_number")
        has_audio = bool(
            slide.pop("audio_storage_key", None) or slide.pop("audio_file", None)
        )
        slide.pop("storage_backend", None)
        if has_audio and isinstance(slide_number, int):
            slide["audio_url"] = (
                f"/api/v1/workspaces/{workspace_id}/artifacts/"
                f"{artifact_id}/slides/{slide_number}/audio"
            )
        else:
            slide["audio_url"] = None
        out.append(slide)
    return out


async def _load_workspace_artifact(
    session: AsyncSession, workspace_id: int, artifact_id: int
) -> tuple[Artifact, Document]:
    row = (
        await session.execute(
            select(Artifact, Document)
            .join(Document, Artifact.document_id == Document.id)
            .options(selectinload(Artifact.files))
            .where(Artifact.id == artifact_id, Artifact.workspace_id == workspace_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return row[0], row[1]


def _list_item(artifact: Artifact, document: Document) -> dict[str, object]:
    item: dict[str, object] = {
        "artifact_id": artifact.id,
        "document_id": artifact.document_id,
        "title": document.title,
        "format": artifact.format,
        "generation": artifact.generation,
        "indexing_status": (document.status or {}).get("state", "ready"),
        "thread_id": artifact.thread_id,
        "created_at": artifact.created_at.isoformat(),
        "updated_at": (
            artifact.updated_at.isoformat() if artifact.updated_at else None
        ),
    }
    legacy = _legacy_ref(artifact)
    if legacy is not None:
        item["legacy"] = legacy
    return item


@router.get("/workspaces/{workspace_id}/artifacts")
async def list_artifacts(
    workspace_id: int,
    response: Response,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    thread_id: int | None = None,
):
    await _authorize_artifact(
        session, auth, workspace_id, Permission.ARTIFACTS_READ, "read"
    )
    query = (
        select(Artifact, Document)
        .join(Document, Artifact.document_id == Document.id)
        .where(Artifact.workspace_id == workspace_id)
    )
    if thread_id is not None:
        query = query.where(Artifact.thread_id == thread_id)
    rows = (
        await session.execute(
            query.order_by(Artifact.updated_at.desc(), Artifact.id.desc())
        )
    ).all()
    response.headers["Cache-Control"] = "private, no-store"
    return [_list_item(artifact, document) for artifact, document in rows]


@router.get("/workspaces/{workspace_id}/artifacts/{artifact_id}/manifest")
async def get_artifact_manifest(
    workspace_id: int,
    artifact_id: int,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    await _authorize_artifact(
        session, auth, workspace_id, Permission.ARTIFACTS_READ, "read"
    )
    row = (
        await session.execute(
            select(Artifact, Document)
            .join(Document, Artifact.document_id == Document.id)
            .options(selectinload(Artifact.files))
            .where(Artifact.id == artifact_id, Artifact.workspace_id == workspace_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    artifact, document = row
    flashcard_study_state = None
    quiz_state = None
    if artifact.format == "flashcards":
        try:
            deck = await _read_flashcard_deck(artifact)
            card_count = len(deck.cards)
        except Exception:
            logger.warning(
                "Could not normalize flashcard state for artifact %s generation %s",
                artifact.id,
                artifact.generation,
                exc_info=True,
            )
            card_count = 0
        flashcard_study_state = sanitize_flashcard_study_state(
            artifact.artifact_metadata,
            user_id=auth.user.id,
            generation=artifact.generation,
            card_count=card_count,
        )
    elif artifact.format == "quiz":
        try:
            quiz = await _read_quiz(artifact)
            question_count = len(quiz.questions)
        except Exception:
            logger.warning(
                "Could not normalize quiz state for artifact %s generation %s",
                artifact.id,
                artifact.generation,
                exc_info=True,
            )
            question_count = 0
        quiz_state = sanitize_quiz_state(
            artifact.artifact_metadata,
            user_id=auth.user.id,
            generation=artifact.generation,
            question_count=question_count,
        )
    etag_suffix = ""
    if flashcard_study_state is not None:
        etag_suffix = f":{study_state_digest(flashcard_study_state)}"
    elif quiz_state is not None:
        etag_suffix = f":{quiz_state_digest(quiz_state)}"
    etag = f'"{document.content_hash}:{artifact.generation}{etag_suffix}"'
    cache_headers = {"ETag": etag, "Cache-Control": "private, no-cache"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=cache_headers)
    response.headers.update(cache_headers)
    payload: dict[str, object] = {
        "artifact_id": artifact.id,
        "document_id": document.id,
        "title": document.title,
        "format": artifact.format,
        "generation": artifact.generation,
        "markdown_representation": document.source_markdown or document.content,
        "files": [
            _file_manifest(workspace_id, artifact.id, file)
            for file in _visible_files(artifact)
        ],
        "updated_at": (
            artifact.updated_at.isoformat() if artifact.updated_at else None
        ),
    }
    legacy = _legacy_ref(artifact)
    if legacy is not None:
        payload["legacy"] = legacy
    if flashcard_study_state is not None:
        payload["flashcard_study_state"] = flashcard_study_state
    if quiz_state is not None:
        payload["quiz_state"] = quiz_state
    return payload


async def _lock_flashcard_mutation(
    session: AsyncSession,
    workspace_id: int,
    artifact_id: int,
    expected_generation: int,
) -> tuple[Artifact, int]:
    source = await session.scalar(
        select(Artifact)
        .options(selectinload(Artifact.files))
        .where(Artifact.id == artifact_id, Artifact.workspace_id == workspace_id)
    )
    if source is None or source.format != "flashcards":
        raise HTTPException(status_code=404, detail="Flashcard artifact not found")
    if source.generation != expected_generation:
        raise HTTPException(
            status_code=409,
            detail="Flashcard artifact generation changed; refresh before updating",
        )
    try:
        card_count = len((await _read_flashcard_deck(source)).cards)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    # ponytail: One short artifact-row lock serializes bounded JSONB writes. Move
    # study state to user-owned rows only if workspace contention becomes material.
    artifact = await session.scalar(
        select(Artifact)
        .where(
            Artifact.id == artifact_id,
            Artifact.workspace_id == workspace_id,
        )
        .with_for_update()
    )
    if (
        artifact is None
        or artifact.format != "flashcards"
        or artifact.generation != expected_generation
    ):
        raise HTTPException(
            status_code=409,
            detail="Flashcard artifact changed; refresh before updating",
        )
    return artifact, card_count


async def _commit_interaction_state(
    session: AsyncSession,
    artifact: Artifact,
    metadata: dict[str, object],
) -> None:
    content_updated_at = artifact.updated_at
    artifact.artifact_metadata = metadata
    artifact.updated_at = content_updated_at
    flag_modified(artifact, "updated_at")
    await session.commit()


@router.patch("/workspaces/{workspace_id}/artifacts/{artifact_id}/flashcard-progress")
async def update_flashcard_progress(
    workspace_id: int,
    artifact_id: int,
    update: FlashcardProgressUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    await _authorize_artifact(
        session, auth, workspace_id, Permission.ARTIFACTS_UPDATE, "update"
    )
    artifact, card_count = await _lock_flashcard_mutation(
        session,
        workspace_id,
        artifact_id,
        update.generation,
    )

    try:
        metadata, state = apply_flashcard_mark(
            artifact.artifact_metadata,
            user_id=auth.user.id,
            generation=artifact.generation,
            card_count=card_count,
            card_index=update.card_index,
            mark=update.mark,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    await _commit_interaction_state(session, artifact, metadata)
    return state


@router.delete("/workspaces/{workspace_id}/artifacts/{artifact_id}/flashcard-progress")
async def reset_artifact_flashcard_progress(
    workspace_id: int,
    artifact_id: int,
    generation: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    await _authorize_artifact(
        session, auth, workspace_id, Permission.ARTIFACTS_UPDATE, "update"
    )
    artifact, card_count = await _lock_flashcard_mutation(
        session,
        workspace_id,
        artifact_id,
        generation,
    )

    metadata, state = reset_flashcard_progress(
        artifact.artifact_metadata,
        user_id=auth.user.id,
        generation=artifact.generation,
        card_count=card_count,
    )
    await _commit_interaction_state(session, artifact, metadata)
    return state


@router.put("/workspaces/{workspace_id}/artifacts/{artifact_id}/flashcard-order")
async def update_flashcard_order(
    workspace_id: int,
    artifact_id: int,
    update: FlashcardOrderUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    await _authorize_artifact(
        session, auth, workspace_id, Permission.ARTIFACTS_UPDATE, "update"
    )
    artifact, card_count = await _lock_flashcard_mutation(
        session,
        workspace_id,
        artifact_id,
        update.generation,
    )
    try:
        metadata, state = apply_flashcard_order(
            artifact.artifact_metadata,
            user_id=auth.user.id,
            generation=artifact.generation,
            card_count=card_count,
            order=update.order,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    await _commit_interaction_state(session, artifact, metadata)
    return state


async def _lock_quiz_mutation(
    session: AsyncSession,
    workspace_id: int,
    artifact_id: int,
    expected_generation: int,
) -> tuple[Artifact, QuizV1]:
    source = await session.scalar(
        select(Artifact)
        .options(selectinload(Artifact.files))
        .where(Artifact.id == artifact_id, Artifact.workspace_id == workspace_id)
    )
    if source is None or source.format != "quiz":
        raise HTTPException(status_code=404, detail="Quiz artifact not found")
    if source.generation != expected_generation:
        raise HTTPException(
            status_code=409,
            detail="Quiz artifact generation changed; refresh before updating",
        )
    try:
        quiz = await _read_quiz(source)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    # ponytail: One short artifact-row lock is sufficient for bounded per-user
    # state. Move progress to user-owned rows if contention becomes material.
    artifact = await session.scalar(
        select(Artifact)
        .where(
            Artifact.id == artifact_id,
            Artifact.workspace_id == workspace_id,
        )
        .with_for_update()
    )
    if (
        artifact is None
        or artifact.format != "quiz"
        or artifact.generation != expected_generation
    ):
        raise HTTPException(
            status_code=409,
            detail="Quiz artifact changed; refresh before updating",
        )
    return artifact, quiz


@router.put("/workspaces/{workspace_id}/artifacts/{artifact_id}/quiz-answer")
async def update_quiz_answer(
    workspace_id: int,
    artifact_id: int,
    update: QuizAnswerUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    await _authorize_artifact(
        session, auth, workspace_id, Permission.ARTIFACTS_UPDATE, "update"
    )
    artifact, quiz = await _lock_quiz_mutation(
        session,
        workspace_id,
        artifact_id,
        update.generation,
    )
    try:
        metadata, state = apply_quiz_answer(
            artifact.artifact_metadata,
            user_id=auth.user.id,
            generation=artifact.generation,
            question_count=len(quiz.questions),
            question_index=update.question_index,
            selected_option_index=update.selected_option_index,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None

    await _commit_interaction_state(session, artifact, metadata)
    return state


@router.put("/workspaces/{workspace_id}/artifacts/{artifact_id}/quiz-skip")
async def skip_quiz_question(
    workspace_id: int,
    artifact_id: int,
    update: QuizSkipUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    await _authorize_artifact(
        session, auth, workspace_id, Permission.ARTIFACTS_UPDATE, "update"
    )
    artifact, quiz = await _lock_quiz_mutation(
        session,
        workspace_id,
        artifact_id,
        update.generation,
    )
    try:
        metadata, state = apply_quiz_skip(
            artifact.artifact_metadata,
            user_id=auth.user.id,
            generation=artifact.generation,
            question_count=len(quiz.questions),
            question_index=update.question_index,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None

    await _commit_interaction_state(session, artifact, metadata)
    return state


@router.post("/workspaces/{workspace_id}/artifacts/{artifact_id}/quiz-retake")
async def retake_quiz(
    workspace_id: int,
    artifact_id: int,
    update: QuizRetakeUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    await _authorize_artifact(
        session, auth, workspace_id, Permission.ARTIFACTS_UPDATE, "update"
    )
    artifact, quiz = await _lock_quiz_mutation(
        session,
        workspace_id,
        artifact_id,
        update.generation,
    )
    try:
        metadata, state = apply_quiz_retake(
            artifact.artifact_metadata,
            user_id=auth.user.id,
            generation=artifact.generation,
            correct_option_indices=[
                question.correct_option_index for question in quiz.questions
            ],
            mode=update.mode,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None

    await _commit_interaction_state(session, artifact, metadata)
    return state


@router.get("/workspaces/{workspace_id}/artifacts/{artifact_id}/download")
async def download_artifact(
    workspace_id: int,
    artifact_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> StreamingResponse:
    await _authorize_artifact(
        session, auth, workspace_id, Permission.ARTIFACTS_READ, "read"
    )
    row = (
        await session.execute(
            select(Artifact, Document)
            .join(Document, Artifact.document_id == Document.id)
            .options(selectinload(Artifact.files))
            .where(Artifact.id == artifact_id, Artifact.workspace_id == workspace_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    artifact, document = row
    primary = next(
        (file for file in artifact.files if file.role is ArtifactFileRole.PRIMARY),
        None,
    )
    headers = {
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
    }
    if primary is not None:
        return StreamingResponse(
            open_artifact_file_stream(primary),
            media_type=primary.mime_type or "application/octet-stream",
            headers={
                **headers,
                "Content-Disposition": _content_disposition(
                    _artifact_filename(document.title, primary.original_filename),
                    inline=False,
                ),
            },
        )
    filename = _markdown_filename(document.title)
    return StreamingResponse(
        io.BytesIO((document.source_markdown or document.content).encode()),
        media_type="text/markdown; charset=utf-8",
        headers={
            **headers,
            "Content-Disposition": _content_disposition(filename, inline=False),
        },
    )


@router.delete("/workspaces/{workspace_id}/artifacts/{artifact_id}", status_code=204)
async def delete_artifact(
    workspace_id: int,
    artifact_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> Response:
    await _authorize_artifact(
        session, auth, workspace_id, Permission.ARTIFACTS_DELETE, "delete"
    )
    row = (
        await session.execute(
            select(Artifact, Document)
            .join(Document, Artifact.document_id == Document.id)
            .where(Artifact.id == artifact_id, Artifact.workspace_id == workspace_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    _, document = row

    document.status = {"state": "deleting"}
    await session.commit()
    try:
        from app.tasks.celery_tasks.document_tasks import delete_document_task

        delete_document_task.delay(document.id)
    except Exception as dispatch_error:
        document.status = {"state": "ready"}
        await session.commit()
        raise HTTPException(
            status_code=503,
            detail="Failed to queue background deletion. Please try again.",
        ) from dispatch_error
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


@router.get("/workspaces/{workspace_id}/artifacts/{artifact_id}/video")
async def get_artifact_video(
    workspace_id: int,
    artifact_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Remotion payload for a video Artifact (slides + scene_codes)."""
    await _authorize_artifact(
        session, auth, workspace_id, Permission.ARTIFACTS_READ, "read"
    )
    artifact, document = await _load_workspace_artifact(
        session, workspace_id, artifact_id
    )
    if artifact.format != "video":
        raise HTTPException(status_code=404, detail="Artifact is not a video")
    meta = artifact.artifact_metadata or {}
    slides = meta.get("slides")
    scene_codes = meta.get("scene_codes")
    if not isinstance(slides, list) or not isinstance(scene_codes, list):
        raise HTTPException(
            status_code=404, detail="Video Remotion payload not available"
        )
    return {
        "artifact_id": artifact.id,
        "title": document.title,
        "status": "ready",
        "slides": _slides_for_remotion(workspace_id, artifact.id, slides),
        "scene_codes": scene_codes,
        "slide_count": len(slides),
        "workspace_id": workspace_id,
        "thread_id": artifact.thread_id,
    }


@router.get(
    "/workspaces/{workspace_id}/artifacts/{artifact_id}/slides/{slide_number}/audio"
)
async def stream_artifact_slide_audio(
    workspace_id: int,
    artifact_id: int,
    slide_number: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    await _authorize_artifact(
        session, auth, workspace_id, Permission.ARTIFACTS_READ, "read"
    )
    artifact, _document = await _load_workspace_artifact(
        session, workspace_id, artifact_id
    )
    if artifact.format != "video":
        raise HTTPException(status_code=404, detail="Artifact is not a video")
    slides = (artifact.artifact_metadata or {}).get("slides") or []
    slide_data = next(
        (
            slide
            for slide in slides
            if isinstance(slide, dict) and slide.get("slide_number") == slide_number
        ),
        None,
    )
    if slide_data is None:
        raise HTTPException(status_code=404, detail=f"Slide {slide_number} not found")
    storage_key = slide_data.get("audio_storage_key")
    if not storage_key:
        raise HTTPException(status_code=404, detail="Slide audio file not found")
    from app.artifacts.media.video import open_stream

    ext = Path(str(storage_key)).suffix.lower()
    media_type = "audio/wav" if ext == ".wav" else "audio/mpeg"
    return StreamingResponse(
        open_stream(str(storage_key)),
        media_type=media_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Disposition": (f"inline; filename={Path(str(storage_key)).name}"),
        },
    )


@router.get(
    "/workspaces/{workspace_id}/artifacts/{artifact_id}/files/{file_id}/content"
)
async def stream_artifact_file(
    workspace_id: int,
    artifact_id: int,
    file_id: int,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> Response:
    await _authorize_artifact(
        session, auth, workspace_id, Permission.ARTIFACTS_READ, "read"
    )
    record = await session.scalar(
        select(ArtifactFile)
        .join(Artifact, ArtifactFile.artifact_id == Artifact.id)
        .where(
            ArtifactFile.id == file_id,
            ArtifactFile.artifact_id == artifact_id,
            Artifact.workspace_id == workspace_id,
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Artifact file not found")

    etag_value = record.checksum_sha256 or f"artifact-file-{record.id}"
    etag = f'"{etag_value}"'
    headers = {
        "ETag": etag,
        "Cache-Control": "private, max-age=31536000, immutable",
        "X-Content-Type-Options": "nosniff",
        "Accept-Ranges": "bytes",
    }
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    mime_type = record.mime_type or "application/octet-stream"
    disposition = _content_disposition(
        record.original_filename, inline=_is_inline(mime_type)
    )
    range_header = request.headers.get("range")
    if range_header:
        try:
            start, end = _parse_range(range_header, record.size_bytes)
        except ValueError:
            return Response(
                status_code=416,
                headers={
                    **headers,
                    "Content-Range": f"bytes */{record.size_bytes}",
                },
            )
        return StreamingResponse(
            open_artifact_file_range(record, start, end),
            status_code=206,
            media_type=mime_type,
            headers={
                **headers,
                "Content-Disposition": disposition,
                "Content-Range": f"bytes {start}-{end}/{record.size_bytes}",
                "Content-Length": str(end - start + 1),
            },
        )
    return StreamingResponse(
        open_artifact_file_stream(record),
        media_type=mime_type,
        headers={
            **headers,
            "Content-Disposition": disposition,
            "Content-Length": str(record.size_bytes),
        },
    )
