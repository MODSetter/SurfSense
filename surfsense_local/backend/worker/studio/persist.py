import hashlib
import shutil

from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact, ArtifactFile, ArtifactFileRole
from modules.documents.models import Document
from shared.config import get_storage_settings
from worker.ingestion import chunking, embedding, indexing
from worker.studio.builders import Built

_EXTENSION = {
    "application/pdf": ".pdf",
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
    document.title = built.title
    document.content = built.markdown
    _index(session, document, built.markdown)
    _write_files(session, artifact, built)


def _index(session: Session, document: Document, markdown: str) -> None:
    passages = chunking.chunk(markdown)
    texts = [passage.text for passage in passages]
    vectors = embedding.embed(texts) if texts else []
    indexing.replace_chunks(session, document, passages, vectors)


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
