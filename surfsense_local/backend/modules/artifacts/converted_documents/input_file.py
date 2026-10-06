"""The file a conversion reads: a ready Word or PowerPoint version's own file, or a source's original."""

from pathlib import Path

from sqlalchemy.orm import Session

from modules.artifacts.converted_documents.conversion import (
    CONVERTIBLE_SUFFIXES,
    Conversion,
)
from modules.artifacts.models import Artifact, ArtifactFileRole
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.documents.original_file import original_path
from shared.config import get_storage_settings


class ConversionRefusedError(Exception):
    """A file this conversion will not read, in a sentence the caller passes on."""


def input_file(
    session: Session, workspace_id: int, conversion: Conversion
) -> tuple[str, Path]:
    """The title to give the PDF and the file to convert.

    The job checks again: the version or source may be gone by then.
    """
    if conversion.artifact_id is not None:
        return _artifact_file(session, workspace_id, conversion.artifact_id)
    if conversion.document_id is None:
        raise ConversionRefusedError("Name the artifact or the source to convert.")
    return _source_file(session, workspace_id, conversion.document_id)


def _artifact_file(
    session: Session, workspace_id: int, artifact_id: int
) -> tuple[str, Path]:
    artifact = session.get(Artifact, artifact_id)
    if artifact is None or artifact.workspace_id != workspace_id:
        raise ConversionRefusedError(
            f"There is no artifact {artifact_id} in this workspace."
        )
    if artifact.format not in ("docx", "pptx"):
        raise ConversionRefusedError(
            f"Artifact {artifact_id} is not a Word document or a PowerPoint deck; "
            "only those convert to PDF."
        )
    if artifact.document.status is not DocumentStatus.READY:
        raise ConversionRefusedError(
            f"Artifact {artifact_id} is not ready yet: convert it once it is."
        )
    primary = next(
        (f for f in artifact.files if f.role is ArtifactFileRole.PRIMARY), None
    )
    path = (
        get_storage_settings().data_dir / primary.storage_key
        if primary is not None
        else None
    )
    if path is None or not path.is_file():
        raise ConversionRefusedError(f"Artifact {artifact_id}'s file is missing.")
    return _title(artifact.document.title), path


def _source_file(
    session: Session, workspace_id: int, document_id: int
) -> tuple[str, Path]:
    document = session.get(Document, document_id)
    if document is None or document.workspace_id != workspace_id:
        raise ConversionRefusedError(
            f"Source {document_id}: not a source in this workspace."
        )
    title = _title(document.title)
    path = (
        original_path(document) if document.document_type is DocumentType.FILE else None
    )
    if path is None:
        raise ConversionRefusedError(
            f'Source {document_id} ("{title}") has no file of its own to convert.'
        )
    if path.suffix.lower() not in CONVERTIBLE_SUFFIXES:
        raise ConversionRefusedError(
            f'Source {document_id} ("{title}") is not a Word (.docx) or PowerPoint '
            "(.pptx) file; only those convert to PDF."
        )
    return title, path


def _title(title: str) -> str:
    return " ".join(title.split())
