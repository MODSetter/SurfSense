import struct

from modules.documents.kindle_books.container import (
    BookHeader,
    DrmProtectedError,
    KindleBookError,
    book_header,
    has_mobi_header,
    records,
)
from worker.ingestion.kindle_books.kf8_files import kf8_files
from worker.ingestion.kindle_books.mobi6_headings import with_headings
from worker.ingestion.kindle_books.mobi6_pages import as_pages
from worker.ingestion.kindle_books.one_document import one_document
from worker.ingestion.kindle_books.plain_text import as_paragraphs
from worker.ingestion.kindle_books.text import book_text

_KF8_VERSION = 8
# What reading a damaged file's offsets and counts can raise.
_DAMAGE = (IndexError, KeyError, ValueError, struct.error, RecursionError)


def book_html(data: bytes) -> str:
    """The book as one HTML document."""
    try:
        return _html(data)
    except KindleBookError:
        raise
    except _DAMAGE as error:
        raise KindleBookError("the book is damaged") from error


def _html(data: bytes) -> str:
    book_records = records(data)
    header = book_header(book_records[0])
    if header.encryption:
        raise DrmProtectedError("the book is DRM-protected")
    if not has_mobi_header(book_records[0]):
        return as_paragraphs(_decoded(book_text(book_records, header), header))
    boundary = header.kf8_boundary
    if header.version < _KF8_VERSION and boundary is not None:
        # A combined file: its KF8 copy keeps the markup its MOBI 6 copy flattens.
        try:
            return _kf8_html(book_records[boundary:])
        except DrmProtectedError:
            raise
        except _DAMAGE:
            pass
    if header.version >= _KF8_VERSION:
        return _kf8_html(book_records)
    return as_pages(with_headings(_decoded(book_text(book_records, header), header)))


def _kf8_html(book_records: list[bytes]) -> str:
    header = book_header(book_records[0])
    if header.encryption:
        raise DrmProtectedError("the book is DRM-protected")
    files = kf8_files(book_records, header)
    return one_document([_decoded(page, header) for page in files])


def _decoded(text: bytes, header: BookHeader) -> str:
    return text.decode(header.encoding, "replace")
