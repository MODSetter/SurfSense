import hashlib
import logging
import shutil

from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact, ArtifactFile, ArtifactFileRole
from modules.documents.models import Document
from modules.embedding.active import ActiveIndex, require_active_index
from shared.config import get_storage_settings
from worker.ingestion import chunking, indexing
from worker.ingestion.chunking import Passage
from worker.studio.shared.artifact import Built

logger = logging.getLogger(__name__)

_EXTENSION = {
    "application/pdf": ".pdf",
    "application/json": ".json",
    "image/png": ".png",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "text/html": ".html",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
}


def persist(
    session: Session, artifact: Artifact, document: Document, built: Built
) -> None:
    """Set the searchable body, index it, and store the rendered blobs.

    The body is a Document (ADR-0003), so it rides the ingestion index like any
    source; the sidecar's files hold only the deliverable bytes.
    """
    logger.info("studio: persist artifact %s indexing", artifact.id)
    index, passages, vectors = _embed(session, built.markdown)
    document.title = built.title
    document.content = built.markdown
    indexing.replace_chunks(session, document, index, passages, vectors)
    logger.info("studio: persist artifact %s writing files", artifact.id)
    _write_files(session, artifact, built)


def _embed(
    session: Session, markdown: str
) -> tuple[ActiveIndex, list[Passage], list[list[float]]]:
    """The body's passages and vectors, embedded with no transaction open.

    Embedding takes as long as the body is long; every other writer would wait on it.
    """
    index = require_active_index(session)
    session.commit()  # the read took the write lock; drop it before embedding
    passages = chunking.chunk(markdown)
    return index, passages, indexing.embed_passages(index, passages)


def _write_files(session: Session, artifact: Artifact, built: Built) -> None:
    if built.primary is None:
        return

    directory = get_storage_settings().artifact_dir(artifact.workspace_id, artifact.id)
    # A re-run replaces the last generation's bytes and rows outright.
    shutil.rmtree(directory, ignore_errors=True)
    directory.mkdir(parents=True, exist_ok=True)
    artifact.files.clear()
    session.flush()

    _write(
        artifact,
        ArtifactFileRole.PRIMARY,
        built.primary,
        built.primary_mime,
        built.primary_filename,
    )
    if built.preview is not None:
        _write(
            artifact,
            ArtifactFileRole.PREVIEW,
            built.preview,
            built.preview_mime,
            built.preview_filename,
        )


def _write(
    artifact: Artifact,
    role: ArtifactFileRole,
    data: bytes,
    mime: str | None,
    filename: str | None,
) -> None:
    storage = get_storage_settings()
    mime = mime or "application/octet-stream"
    suffix = _EXTENSION.get(mime, "")
    path = storage.artifact_dir(artifact.workspace_id, artifact.id) / f"{role}{suffix}"
    path.write_bytes(data)

    artifact.files.append(
        ArtifactFile(
            role=role,
            storage_key=str(path.relative_to(storage.data_dir)),
            original_filename=filename or f"{artifact.format}-{artifact.id}{suffix}",
            mime_type=mime,
            size_bytes=len(data),
            checksum_sha256=hashlib.sha256(data).hexdigest(),
        )
    )
