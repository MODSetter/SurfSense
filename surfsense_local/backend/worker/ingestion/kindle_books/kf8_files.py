from modules.documents.kindle_books.container import BookHeader, KindleBookError
from worker.ingestion.kindle_books.kf8_index import index_entries
from worker.ingestion.kindle_books.text import book_text

_FRAGMENT_COUNT, _POSITION = 1, 6


def kf8_files(book_records: list[bytes], header: BookHeader) -> list[bytes]:
    """A KF8 book's XHTML files in reading order. The text holds each file's
    skeleton followed by its fragments, which go back in at the points the
    fragment index names."""
    text = book_text(book_records, header)
    skeletons = index_entries(book_records, header.skel_index)
    fragments = index_entries(book_records, header.frag_index)
    files = []
    next_fragment = 0
    # Each byte of text belongs to one file, once; more means a crafted index.
    budget = len(text)
    for _, skeleton in skeletons:
        count = skeleton[_FRAGMENT_COUNT][0]
        start, length = skeleton[_POSITION][:2]
        page = bytearray(text[start : start + length])
        if len(page) > budget:
            raise KindleBookError("the book's skeleton index is damaged")
        for name, fragment in fragments[next_fragment : next_fragment + count]:
            # Insert points count the fragments already in, so they go in order.
            insert_at = int(name) - start
            piece_at = start + length + fragment[_POSITION][0]
            if not 0 <= insert_at <= len(page):
                raise KindleBookError("the book's fragment index is damaged")
            page[insert_at:insert_at] = text[
                piece_at : piece_at + fragment[_POSITION][1]
            ]
            if len(page) > budget:
                raise KindleBookError("the book's fragment index is damaged")
        next_fragment += count
        budget -= len(page)
        files.append(bytes(page))
    return files
