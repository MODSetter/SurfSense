"""A file a tool made itself, kept as a new artifact; Studio's job only reads and indexes it.

The tool has the bytes before the artifact exists, so the file is stored at
once and the artifact is usable straight away; the job adds the searchable
body (ADR-0003). It records what made it and what it came from, and keeps no
spec, so it is a document of its own and never a version of its inputs.
"""

import hashlib
import logging
from typing import Any

from pathvalidate import sanitize_filename
from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact, ArtifactFile, ArtifactFileRole
from modules.artifacts.tasks import studio_job
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.embedding.active import EmbeddingNotChosenError, require_active_index
from shared.config import get_storage_settings

logger = logging.getLogger(__name__)

MADE_KEY = "made_by"
TITLE_CHARS = 200
MIME = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


class MadeFileRefusedError(Exception):
    """A file this service will not keep, in a sentence the caller passes on."""


def made_by(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    """What made an artifact's file, for one a tool made; None for any other."""
    made = (metadata or {}).get(MADE_KEY)
    return made if isinstance(made, dict) else None


def keep_made_file(
    session: Session,
    workspace_id: int,
    *,
    title: str,
    format: str,
    data: bytes,
    made_by: dict[str, Any],
    document_ids: list[int],
    artifact_ids: list[int],
    chat_thread_id: int | None,
) -> Artifact:
    """Store the file as a new pending artifact and queue the job that indexes it.

    Commits before enqueueing: the worker is another process and must find the row.
    """
    title = " ".join(title.split())
    if not 1 <= len(title) <= TITLE_CHARS:
        raise MadeFileRefusedError(f"Give a title of 1 to {TITLE_CHARS} characters.")
    # The job indexes the file; failing there would leave a file nobody can find.
    try:
        require_active_index(session)
    except EmbeddingNotChosenError as error:
        raise MadeFileRefusedError(
            "Studio is not ready on this computer: no embedding model is chosen yet."
        ) from error
    document = Document(
        workspace_id=workspace_id,
        title=title,
        document_type=DocumentType.ARTIFACT,
        status=DocumentStatus.PENDING,
    )
    session.add(document)
    session.flush()
    artifact = Artifact(
        document_id=document.id,
        workspace_id=workspace_id,
        format=format,
        chat_thread_id=chat_thread_id,
        artifact_metadata={
            MADE_KEY: made_by,
            "derived_from": {
                "document_ids": list(document_ids),
                "artifact_ids": list(artifact_ids),
            },
            "source_document_ids": list(document_ids),
            "prompt": None,
        },
    )
    session.add(artifact)
    session.flush()
    artifact.files.append(_stored(artifact, title, format, data))
    session.commit()
    studio_job(artifact.id)
    logger.info("studio: kept made %s file as artifact %s", format, artifact.id)
    return artifact


def _stored(artifact: Artifact, title: str, format: str, data: bytes) -> ArtifactFile:
    """The bytes where Studio's job keeps a primary file, and their row."""
    storage = get_storage_settings()
    folder = storage.artifact_dir(artifact.workspace_id, artifact.id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{ArtifactFileRole.PRIMARY}.{format}"
    path.write_bytes(data)
    stem = sanitize_filename(title, platform="universal") or "document"
    return ArtifactFile(
        role=ArtifactFileRole.PRIMARY,
        storage_key=str(path.relative_to(storage.data_dir)),
        original_filename=f"{stem}.{format}",
        mime_type=MIME.get(format, "application/octet-stream"),
        size_bytes=len(data),
        checksum_sha256=hashlib.sha256(data).hexdigest(),
    )
