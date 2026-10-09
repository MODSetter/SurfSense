"""Convert a Word file or deck to PDF with LibreOffice, shaped into a Built."""

import time
from pathlib import Path

from modules.office_support import OfficeRunError, engine
from worker.studio.office.pdf import pdf as pdf_format
from worker.studio.script_document.extracted_text import (
    UnreadableDocumentError,
    pdf_text,
)
from worker.studio.shared.artifact import Built
from worker.studio.shared.text import file_stem

# LibreOffice's lock wait ends 20 s before this and a conversion gets 90 s at
# most; the convert tool waits 150 s for the job.
CONVERT_SECONDS = 120


class ConversionFailedError(RuntimeError):
    """No PDF came out, said in a sentence the convert tool passes on."""


def convert(title: str, file: Path) -> Built:
    """A PDF of `file`, which is only read: LibreOffice converts a copy."""
    office = engine.office_engine()
    if office is None:
        raise ConversionFailedError(
            "Office support is off, so nothing can convert this file to PDF."
        )
    try:
        pdf = office.pdf_of(file, deadline=time.monotonic() + CONVERT_SECONDS)
        text = pdf_text(pdf)
    except OfficeRunError as error:
        raise ConversionFailedError(str(error)) from error
    except UnreadableDocumentError as error:
        raise ConversionFailedError("LibreOffice wrote no readable PDF.") from error
    return Built(
        title=title,
        markdown=text or f"# {title}",
        primary=pdf,
        primary_mime=pdf_format.mime,
        primary_filename=f"{file_stem(title, pdf_format.stem)}.{pdf_format.ext}",
    )
