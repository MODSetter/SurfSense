"""The user's file a revised copy starts from: a source's original, opened only to read."""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from modules.artifacts.revised_copies.formats import (
    SUFFIXES_SENTENCE,
    RevisableFormat,
    revisable_format,
)
from modules.artifacts.revised_copies.refusals import RevisedCopyRefusedError
from modules.documents.models import Document, DocumentType
from modules.documents.original_file import original_path


@dataclass(frozen=True)
class SourceFile:
    document_id: int
    path: Path
    format: RevisableFormat


def source_file(session: Session, workspace_id: int, document_id: int) -> SourceFile:
    """The source's original, refused unless it is a file on disk of a revisable kind."""
    document = session.get(Document, document_id)
    if (
        document is None
        or document.workspace_id != workspace_id
        or document.document_type is not DocumentType.FILE
    ):
        raise RevisedCopyRefusedError(
            f"There is no source file {document_id} in this workspace to revise."
        )
    path = original_path(document)
    if path is None:
        raise RevisedCopyRefusedError(
            f"Source {document_id}'s file is no longer on disk, so it cannot be revised."
        )
    fmt = revisable_format(path)
    if fmt is None:
        raise RevisedCopyRefusedError(
            f'Source {document_id} ("{path.name}") is a {path.suffix or "file"} '
            f"file. {SUFFIXES_SENTENCE}"
        )
    return SourceFile(document_id, path, fmt)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()
