"""The PDFs a PDF tool call names: ticked sources and the workspace's PDF artifacts, read only.

A source is held to the turn's ticked sources; an artifact is the agent's or
Studio's output, so any turn of the workspace may use it, as a render may.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pypdf
from sqlalchemy.orm import Session

from modules.agent.thread_folder.layout import SOURCES
from modules.agent.tool_endpoint.tool import ToolCallError
from modules.agent.tool_endpoint.turn_scope import TurnScope
from modules.artifacts.models import Artifact, ArtifactFileRole
from modules.artifacts.script_documents.spec import FORMAT_NAMES
from modules.documents.models import Document, DocumentType
from modules.documents.original_file import original_path
from modules.pdf_tools import opened_pdf
from modules.pdf_tools.refusal import PdfRefusedError
from shared.config import get_storage_settings

WHICH_SOURCE = f"the number in brackets at the end of its file name in {SOURCES}/"


@dataclass(frozen=True)
class PdfInput:
    """One PDF a call named, where its bytes are, and how sentences name it."""

    name: str  # 'Source 7 ("Report.pdf")', to start a sentence
    title: str  # what a new artifact's title starts from
    path: Path
    document_id: int | None = None
    artifact_id: int | None = None

    def reader(self) -> pypdf.PdfReader:
        """The PDF opened, or the reason it cannot be, as the model reads it."""
        try:
            opened_pdf.refuse_too_large(self.path.stat().st_size, self.name)
            return opened_pdf.open_pdf(self.path.read_bytes(), self.name)
        except FileNotFoundError as error:
            raise ToolCallError(f"{self.name} is no longer on disk.") from error
        except PdfRefusedError as refused:
            raise ToolCallError(str(refused)) from refused

    @property
    def mention(self) -> str:
        """The name inside a sentence."""
        return self.name[0].lower() + self.name[1:]


def readers(inputs: list[PdfInput]) -> list[pypdf.PdfReader]:
    """Each PDF opened; refused before any is read when together they pass the
    size one PDF may have, since every one is held in memory at once."""
    try:
        total = sum(pdf.path.stat().st_size for pdf in inputs)
    except FileNotFoundError:
        total = 0  # each one's own read says which is gone
    if len(inputs) > 1 and total > opened_pdf.MAX_BYTES:
        raise ToolCallError(
            f"These PDFs are {total / 1024 / 1024:,.0f} MB together, more than the "
            f"PDF tools take in one call ({opened_pdf.MAX_BYTES // 1024 // 1024} MB). "
            "Merge fewer at a time."
        )
    return [pdf.reader() for pdf in inputs]


def ids(arguments: dict[str, Any], key: str) -> list[int]:
    """A list of ids, in the order given; one bare id is taken as a list of one."""
    value = arguments.get(key)
    if value is None:
        return []
    if _is_id(value):
        return [value]
    if isinstance(value, list) and all(_is_id(item) for item in value):
        return list(dict.fromkeys(value))
    raise ToolCallError(f"{key} must be a list of numbers, or left out.")


def one_pdf(arguments: dict[str, Any]) -> tuple[list[int], list[int]]:
    """The one PDF a single-PDF tool works on: a document_id or an artifact_id."""
    document_id = arguments.get("document_id")
    artifact_id = arguments.get("artifact_id")
    for key, value in (("document_id", document_id), ("artifact_id", artifact_id)):
        if value is not None and not _is_id(value):
            raise ToolCallError(f"{key} must be a number.")
    if (document_id is None) == (artifact_id is None):
        raise ToolCallError(
            f"Name one PDF: a source's document_id, {WHICH_SOURCE}, or the "
            "artifact_id of a PDF in Studio."
        )
    return (
        [document_id] if document_id is not None else [],
        [artifact_id] if artifact_id is not None else [],
    )


def located(
    session: Session, scope: TurnScope, document_ids: list[int], artifact_ids: list[int]
) -> list[PdfInput]:
    """Each PDF named, sources first; the read's transaction ends before any file work."""
    try:
        scope.refuse_unselected(document_ids)
        found = [_source(session, scope.workspace_id, i) for i in document_ids]
        found += [_artifact(session, scope.workspace_id, i) for i in artifact_ids]
    except ToolCallError:
        session.rollback()
        raise
    session.commit()
    return found


def _source(session: Session, workspace_id: int, document_id: int) -> PdfInput:
    document = session.get(Document, document_id)
    if document is None or document.workspace_id != workspace_id:
        raise ToolCallError(f"Source {document_id}: not a source in this workspace.")
    title = " ".join(document.title.split())
    name = f'Source {document_id} ("{title}")'
    path = (
        original_path(document) if document.document_type is DocumentType.FILE else None
    )
    if path is None or path.suffix.lower() != ".pdf":
        raise ToolCallError(f"{name} is not a PDF.")
    stem = title[:-4] if title.lower().endswith(".pdf") else title
    return PdfInput(name, stem or title, path, document_id=document_id)


def _artifact(session: Session, workspace_id: int, artifact_id: int) -> PdfInput:
    artifact = session.get(Artifact, artifact_id)
    if artifact is None or artifact.workspace_id != workspace_id:
        raise ToolCallError(f"There is no artifact {artifact_id} in this workspace.")
    title = " ".join(artifact.document.title.split())
    name = f'Artifact {artifact_id} ("{title}")'
    if artifact.format != "pdf":
        kind = FORMAT_NAMES.get(artifact.format, artifact.format)
        raise ToolCallError(f"{name} is a {kind}, not a PDF.")
    primary = next(
        (f for f in artifact.files if f.role is ArtifactFileRole.PRIMARY), None
    )
    if primary is None:
        raise ToolCallError(f"{name} has no file yet: it is not ready in Studio.")
    path = get_storage_settings().data_dir / primary.storage_key
    return PdfInput(name, title, path, artifact_id=artifact_id)


def _is_id(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)
