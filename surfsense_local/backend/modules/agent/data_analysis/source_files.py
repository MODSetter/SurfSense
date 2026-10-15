"""The ticked sources an analysis reads: each one's original spreadsheet or CSV file, never written."""

from sqlalchemy.orm import Session

from modules.agent.thread_folder.layout import SOURCES
from modules.documents.models import Document, DocumentType
from modules.documents.original_file import original_path
from worker.document_script.analysis_folder import AnalysisInput

# What pandas reads with what SurfSense ships: .xls needs xlrd, which it does not.
TABLE_SUFFIXES = (".xlsx", ".csv", ".tsv")


class SourceRefusedError(Exception):
    """A source an analysis cannot read, said in a sentence the model can act on."""


def analysis_inputs(
    session: Session, workspace_id: int, document_ids: list[int]
) -> list[AnalysisInput]:
    """Each named source's original file, in the order named; the caller has checked the scope."""
    return [
        _input(session, workspace_id, document_id)
        for document_id in dict.fromkeys(document_ids)
    ]


def _input(session: Session, workspace_id: int, document_id: int) -> AnalysisInput:
    document = session.get(Document, document_id)
    if document is None or document.workspace_id != workspace_id:
        raise SourceRefusedError(
            f"Source {document_id}: not a source in this workspace."
        )
    title = " ".join(document.title.split())
    path = (
        original_path(document) if document.document_type is DocumentType.FILE else None
    )
    named = f'Source {document_id} ("{title}")'
    if path is None:
        raise SourceRefusedError(
            f"{named} has no file of its own: read its text in {SOURCES}/ instead."
        )
    suffix = path.suffix.lower()
    if suffix == ".xls":
        raise SourceRefusedError(
            f"{named} is an old .xls workbook, which SurfSense cannot read: ask the "
            "user to save it as .xlsx."
        )
    if suffix not in TABLE_SUFFIXES:
        raise SourceRefusedError(
            f"{named} is not a spreadsheet or CSV file (.xlsx, .csv or .tsv): read "
            f"its text in {SOURCES}/ instead."
        )
    return AnalysisInput(
        path=path, name=path.name, document_id=document_id, title=title
    )
