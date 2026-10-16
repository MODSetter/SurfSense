"""The order an upload's files are queued in, so the quickest are usable first."""

from collections.abc import Iterable

from modules.documents.models import Document
from modules.documents.recordings.kind import is_recording
from modules.documents.text_files import TEXT_SUFFIXES


def cheapest_first(documents: Iterable[Document]) -> list[Document]:
    """Text, then other files smallest first, then recordings, which take longest.

    Huey runs equal priorities first in, first out, so this is the order a
    dropped batch becomes ready in.
    """
    return sorted(documents, key=_cost)


def _cost(document: Document) -> tuple[int, int]:
    metadata = document.document_metadata or {}
    if is_recording(document.mime_type):
        kind = 2
    elif metadata.get("suffix") in TEXT_SUFFIXES:
        # Read straight off disk, so ready in about a second at any size.
        kind = 0
    else:
        kind = 1
    return kind, int(metadata.get("size_bytes") or 0)
