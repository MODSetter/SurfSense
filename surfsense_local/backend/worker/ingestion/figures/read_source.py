"""The ready source a figures pass reads, and whether it is still there after.

Delete is refused only while a source is processing, so a ready one can go
mid-pass. On Windows the delete cannot remove the file Docling holds open, and
SQLite gives the highest id out again once its row is gone, so the next
document would find that file in its folder.
"""

import os
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from sqlalchemy.orm import Session

from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.documents.original_file import original_path
from shared.config import get_storage_settings
from shared.db import create_db_engine, create_session_factory


class ReadSource(NamedTuple):
    document_id: int
    original: Path
    # Which row and which file were read, since a later document can take the id.
    row: tuple[datetime, str | None]
    file: os.stat_result


def ready_source(document_id: int) -> ReadSource | None:
    with _session() as session:
        document = session.get(Document, document_id)
        if (
            document is None
            or document.document_type is not DocumentType.FILE
            or document.status is not DocumentStatus.READY
        ):
            return None
        original = original_path(document)
        if original is None:
            return None
        try:
            return ReadSource(document_id, original, _row(document), original.stat())
        except OSError:
            return None


def still_ready(source: ReadSource) -> bool:
    """Asked once Docling has let go of the file. False when the source was
    deleted meanwhile, after removing what the delete could not."""
    folder = source.original.parent
    with _session() as session:
        document = session.get(Document, source.document_id)
        if document is not None and _row(document) == source.row:
            return (
                document.status is DocumentStatus.READY
                and original_path(document) == source.original
            )
        taken = document is not None and _folder(document) == folder
    if not taken:
        shutil.rmtree(folder, ignore_errors=True)
    elif _unchanged(source):
        # A later upload has the id and the folder: only the deleted file goes.
        source.original.unlink(missing_ok=True)
    return False


def _row(document: Document) -> tuple[datetime, str | None]:
    return document.created_at, document.dedup_key


def _folder(document: Document) -> Path:
    return get_storage_settings().document_dir(document.workspace_id, document.id)


def _unchanged(source: ReadSource) -> bool:
    # Not a later upload's file of the same name, where the delete removed the old.
    try:
        return os.path.samestat(source.file, source.original.stat())
    except OSError:
        return False


@contextmanager
def _session() -> Iterator[Session]:
    # No transaction is held while Docling reads: that takes minutes on a long PDF.
    engine = create_db_engine(get_storage_settings().database_path)
    try:
        with create_session_factory(engine)() as session:
            yield session
    finally:
        engine.dispose()
