"""A PDF opened for the PDF tools, or refused in a sentence naming it."""

from io import BytesIO

import pypdf
from pypdf import PasswordType
from pypdf.errors import DependencyError

from modules.pdf_tools.refusal import PdfRefusedError

# pypdf holds every object in memory, and each call must answer inside the
# tool's 200 s; a 1,000-page merge or stamp takes a few seconds.
MAX_PAGES = 1000
MAX_BYTES = 200 * 1024 * 1024


def open_pdf(data: bytes, name: str) -> pypdf.PdfReader:
    """The PDF in `data`; `name` is how a refusal names it, such as 'Source 7 ("Plan.pdf")'.

    An encrypted PDF opens only when its user password is empty: owner-only
    locks open in every viewer without asking.
    """
    refuse_too_large(len(data), name)
    try:
        reader = pypdf.PdfReader(BytesIO(data), strict=False)
        if reader.is_encrypted and _unlock(reader, name) is PasswordType.NOT_DECRYPTED:
            raise PdfRefusedError(
                f"{name} is protected by a password, so the PDF tools cannot open it. "
                "Ask the user for a copy without the password."
            )
        count = len(reader.pages)
    except PdfRefusedError:
        raise
    # A damaged file fails anywhere in pypdf's parser, with any exception type.
    except Exception as error:
        raise PdfRefusedError(
            f"{name} could not be read as a PDF: it may be damaged or not a PDF."
        ) from error
    if count == 0:
        raise PdfRefusedError(f"{name} has no pages.")
    if count > MAX_PAGES:
        raise PdfRefusedError(
            f"{name} has {count:,} pages; the PDF tools work on files of at most "
            f"{MAX_PAGES:,} pages."
        )
    return reader


def refuse_too_large(size: int, name: str) -> None:
    """Refuse a file past MAX_BYTES, before its bytes are read."""
    if size > MAX_BYTES:
        raise PdfRefusedError(
            f"{name} is {size / 1024 / 1024:,.0f} MB, larger than the PDF tools "
            f"take ({MAX_BYTES // 1024 // 1024} MB)."
        )


def _unlock(reader: pypdf.PdfReader, name: str) -> PasswordType:
    try:
        return reader.decrypt("")
    except (DependencyError, NotImplementedError) as error:
        raise PdfRefusedError(
            f"{name} uses an encryption the PDF tools cannot open. Ask the user for "
            "a copy without the password."
        ) from error
