"""A made file's Built: the kept bytes as they are, and their text as the body.

No model is asked and nothing is rendered, so a run and a Regenerate read the
same file.
"""

from collections.abc import Callable

from modules.artifacts.models import Artifact, ArtifactFileRole
from modules.artifacts.script_documents.spec import FORMAT_NAMES
from modules.artifacts.web_pages.page_text import page_text
from shared.config import get_storage_settings
from worker.studio.script_document.deck_text import deck_text
from worker.studio.script_document.extracted_text import (
    UnreadableDocumentError,
    pdf_text,
    word_text,
)
from worker.studio.script_document.workbook_summary import workbook_summary
from worker.studio.shared.artifact import Built


def _page_text(data: bytes) -> str:
    try:
        return page_text(data.decode("utf-8"))
    except UnicodeDecodeError as error:
        raise UnreadableDocumentError("not UTF-8") from error


_TEXT: dict[str, Callable[[bytes], str]] = {
    "pdf": pdf_text,
    "docx": word_text,
    "pptx": deck_text,
    "xlsx": workbook_summary,
    "html": _page_text,
}


class MadeFileUnreadableError(RuntimeError):
    """The kept file is missing or does not open as its format."""


def built(artifact: Artifact, title: str) -> Built:
    """The kept primary file and its text; the job rewrites the same bytes."""
    primary = next(
        (f for f in artifact.files if f.role is ArtifactFileRole.PRIMARY), None
    )
    name = FORMAT_NAMES.get(artifact.format, artifact.format)
    if primary is None:
        raise MadeFileUnreadableError("The kept file is missing.")
    path = get_storage_settings().data_dir / primary.storage_key
    try:
        data = path.read_bytes()
    except FileNotFoundError as error:
        raise MadeFileUnreadableError("The kept file is missing.") from error
    try:
        text = _TEXT[artifact.format](data)
    except (KeyError, UnreadableDocumentError) as error:
        raise MadeFileUnreadableError(
            f"The kept file does not open as a {name}."
        ) from error
    return Built(
        title=title,
        markdown=text or f"# {title}",
        primary=data,
        primary_mime=primary.mime_type,
        primary_filename=primary.original_filename,
    )
