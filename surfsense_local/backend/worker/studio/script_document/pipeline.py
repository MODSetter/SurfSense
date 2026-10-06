"""Run a stored document script and shape what it wrote into a Built.

No model is asked: the script is the document's source, so a run, a retry
and a regenerate all render the same spec.
"""

import logging
from pathlib import Path

from sqlalchemy.orm import Session

from modules.agent.data_analysis.chart_names import is_chart_name
from modules.artifacts.script_documents.script_images import script_image_file
from modules.artifacts.script_documents.spec import DocumentScript
from modules.artifacts.script_documents.template_source import (
    TemplateRefusedError,
    template_file,
)
from worker.document_script.run import run_document_script
from worker.studio.office.docx import docx
from worker.studio.office.pdf import pdf
from worker.studio.office.pptx import pptx
from worker.studio.office.spec import Office
from worker.studio.office.xlsx import xlsx
from worker.studio.script_document.deck_text import deck_text
from worker.studio.script_document.extracted_text import (
    UnreadableDocumentError,
    pdf_text,
    word_text,
)
from worker.studio.script_document.workbook_summary import workbook_summary
from worker.studio.shared.artifact import Built
from worker.studio.shared.text import file_stem

logger = logging.getLogger(__name__)

_OFFICE: dict[str, Office] = {"docx": docx, "pdf": pdf, "pptx": pptx, "xlsx": xlsx}
# The body Studio indexes, and the text the agent's render result shows.
_TEXT = {
    "docx": word_text,
    "pdf": pdf_text,
    "pptx": deck_text,
    "xlsx": workbook_summary,
}


class ScriptRunFailedError(RuntimeError):
    """The script, or the file it wrote, failed; running it again fails the same way."""

    def __init__(self, error: str, traceback_tail: str | None = None) -> None:
        super().__init__(error)
        self.error = error
        self.traceback_tail = traceback_tail

    def reason(self, limit: int) -> str:
        """The error, then as many of the traceback's last lines as fit.

        The last lines name the script's failing line; the first are runpy's frames.
        """
        kept: list[str] = []
        room = limit - len(self.error)
        for line in reversed((self.traceback_tail or "").strip().splitlines()):
            room -= len(line) + 1
            if room < 0:
                break
            kept.insert(0, line)
        return "\n".join([self.error, *kept])[:limit]


def images_for(
    session: Session, workspace_id: int, thread_id: int | None, script: DocumentScript
) -> dict[str, Path]:
    """The PNG of every image the script names, a source's figure or its chat's
    analysis chart, to copy beside it."""
    images: dict[str, Path] = {}
    for name in script.images:
        try:
            images[name] = script_image_file(session, workspace_id, thread_id, name)
        except LookupError as error:
            gone = (
                f'the analysis chart "{name}" is no longer in its chat'
                if is_chart_name(name)
                else f'the source image "{name}" is no longer in this workspace'
            )
            raise ScriptRunFailedError(gone) from error
    return images


def template_for(
    session: Session, workspace_id: int, script: DocumentScript
) -> Path | None:
    """The source file the script starts from, to copy beside it; None without one.

    Checked again here: the source may have been deleted since the version was made.
    """
    if script.template_source_id is None:
        return None
    try:
        return template_file(
            session, workspace_id, script.template_source_id, script.format
        )
    except TemplateRefusedError as refused:
        raise ScriptRunFailedError(
            f"the template cannot be used: {refused}"
        ) from refused


def render(
    title: str,
    script: DocumentScript,
    images: dict[str, Path],
    template: Path | None = None,
) -> Built:
    """Run the script; `template` is the source file copied to TEMPLATE_PATH, if any."""
    office = _OFFICE[script.format]
    result = run_document_script(
        script.text,
        output_name=f"document.{office.ext}",
        images=images,
        template=template,
    )
    logger.info("studio: document script ok=%s in %.1fs", result.ok, result.seconds)
    if not result.ok or result.output is None:
        raise ScriptRunFailedError(
            result.error or "the script failed", result.traceback_tail
        )
    try:
        text = _TEXT[script.format](result.output)
    except UnreadableDocumentError as error:
        raise ScriptRunFailedError(
            f"the script wrote a file that is not a valid .{office.ext}"
        ) from error
    return Built(
        title=title,
        markdown=text or f"# {title}",
        primary=result.output,
        primary_mime=office.mime,
        primary_filename=f"{file_stem(title, office.stem)}.{office.ext}",
    )
