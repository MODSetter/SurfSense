"""Image sources that retrieval found, as pictures for a model that can see them.

OCR keeps an image source's words; the picture keeps the layout, handwriting and
drawings it drops. Read from the stored original at question time, so sources
indexed before this need nothing, and never stored with the turn.
"""

from collections.abc import Sequence
from pathlib import Path

from sqlalchemy.orm import Session

from modules.chat.images.intake import ImageRefusedError, NormalisedImage, normalise
from modules.documents.models import Document, DocumentType
from modules.documents.original_file import original_path
from shared.search import Hit

__all__ = ["MAX_SOURCE_IMAGES", "image_source_paths", "load_source_images"]

# Per turn, the highest ranked, so a pile of screenshots cannot fill the window.
MAX_SOURCE_IMAGES = 2


def image_source_paths(session: Session, hits: Sequence[Hit], limit: int) -> list[Path]:
    """The originals of the best-ranked distinct image sources among the hits."""
    paths: list[Path] = []
    seen: set[int] = set()
    for hit in hits:
        if len(paths) >= limit:
            break
        if hit.document_id in seen:
            continue
        seen.add(hit.document_id)
        document = session.get(Document, hit.document_id)
        if document is None or document.document_type is not DocumentType.FILE:
            continue
        mime = (document.document_metadata or {}).get("mime_type") or ""
        if mime.startswith("image/") and (path := original_path(document)):
            paths.append(path)
    return paths


def load_source_images(paths: Sequence[Path]) -> list[NormalisedImage]:
    """Normalised like an attachment; one that cannot be read is left out."""
    images = []
    for path in paths:
        try:
            images.append(normalise(path.read_bytes()))
        except (OSError, ImageRefusedError):
            continue
    return images
