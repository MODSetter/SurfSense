"""The source file a Word document or a deck starts from, so it keeps that file's look.

Only the original the user uploaded qualifies, and only of the format's own
kind: a .docx for Word, a .pptx for PowerPoint. The runner gets a copy.
"""

from pathlib import Path

from sqlalchemy.orm import Session

from modules.artifacts.script_documents.spec import FORMAT_NAMES
from modules.documents.models import Document, DocumentType
from modules.documents.original_file import original_path

# The formats a template applies to, and the one kind of file each starts from.
TEMPLATE_KINDS: dict[str, tuple[str, str]] = {
    "docx": (".docx", "Word"),
    "pptx": (".pptx", "PowerPoint"),
}


class TemplateRefusedError(Exception):
    """A source that cannot be this document's template, in a sentence the agent reads."""


def template_file(
    session: Session, workspace_id: int, source_id: int, format: str
) -> Path:
    """The source's original file, when it can be a template for this format."""
    kind = TEMPLATE_KINDS.get(format)
    if kind is None:
        raise TemplateRefusedError(
            "A template applies to a Word document or a PowerPoint deck only: "
            f"render the {FORMAT_NAMES[format]} without template_source_id."
        )
    suffix, label = kind
    document = session.get(Document, source_id)
    if (
        document is None
        or document.workspace_id != workspace_id
        or document.document_type is not DocumentType.FILE
    ):
        raise TemplateRefusedError(
            f"There is no source file {source_id} in this workspace to start from."
        )
    path = original_path(document)
    if path is None:
        raise TemplateRefusedError(
            f"Source {source_id}'s file is no longer on disk, so nothing can start "
            "from it."
        )
    if path.suffix.lower() != suffix:
        raise TemplateRefusedError(
            f'Source {source_id} ("{document.title}") is not a {label} file '
            f"({suffix}), so a {FORMAT_NAMES[format]} cannot start from it."
        )
    return path
