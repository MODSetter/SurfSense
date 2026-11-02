from collections.abc import Callable

from modules.documents.kindle_books.container import (
    COMPRESSION_HUFFCDIC,
    COMPRESSION_NONE,
    COMPRESSION_PALMDOC,
    BookHeader,
    KindleBookError,
)
from worker.ingestion.kindle_books.huffcdic import huffcdic_decompressor
from worker.ingestion.kindle_books.palmdoc import palmdoc_decompress
from worker.ingestion.kindle_books.trailing_entries import without_trailing_entries


def book_text(book_records: list[bytes], header: BookHeader) -> bytes:
    """The book's text: its text records, which follow record 0, unpacked and joined."""
    decompress = _decompressor(book_records, header)
    return b"".join(
        decompress(without_trailing_entries(record, header.trailing_flags))
        for record in book_records[1 : 1 + header.text_records]
    )


def _decompressor(
    book_records: list[bytes], header: BookHeader
) -> Callable[[bytes], bytes]:
    if header.compression == COMPRESSION_NONE:
        return bytes
    if header.compression == COMPRESSION_PALMDOC:
        return palmdoc_decompress
    if header.compression == COMPRESSION_HUFFCDIC:
        first = header.huff_record
        return huffcdic_decompressor(book_records[first : first + header.huff_count])
    raise KindleBookError("the book's compression is unknown")
