"""An ingest whose own code the OS will not load, as Windows' Smart App Control
refuses an unsigned native module (#2366): the source fails with the reason
instead of waiting for ever, and is not tried twice more to fail the same way."""

import sqlite3
import sys
from collections.abc import Sequence
from importlib.abc import MetaPathFinder
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import ModuleType

import pytest
from huey.exceptions import CancelExecution
from sqlalchemy import Engine

from modules.documents.docling_batches.layout import batches_dir, ocr_dir
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.documents.recordings.layout import work_files
from modules.documents.tasks import ingest_document
from modules.workspaces.models import Workspace
from shared.config import get_storage_settings
from shared.db import create_session_factory

pytestmark = pytest.mark.integration

# The worker's log in #2366.
REFUSED = (
    "DLL load failed while importing _chunk: "
    "An Application Control policy has blocked this file."
)


class _RefusedPipeline(MetaPathFinder):
    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None,
        target: ModuleType | None = None,
    ) -> ModuleSpec | None:
        if fullname == "worker.ingestion":
            raise ImportError(REFUSED, name="chonkie_core._chunk")
        return None


@pytest.fixture
def refused_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Importing the pipeline fails as it did on the reporter's machine."""
    monkeypatch.delitem(sys.modules, "worker.ingestion", raising=False)
    monkeypatch.setattr(sys, "meta_path", [_RefusedPipeline(), *sys.meta_path])


def _pending_note(engine: Engine, status: DocumentStatus) -> int:
    with create_session_factory(engine)() as session:
        workspace = Workspace(name="w")
        session.add(workspace)
        session.flush()
        note = Document(
            workspace_id=workspace.id,
            title="notes",
            document_type=DocumentType.NOTE,
            content="# Notes",
            status=status,
        )
        session.add(note)
        session.commit()
        return note.id


def _parked_file(engine: Engine, name: str, mime_type: str) -> tuple[int, Path]:
    """A file that gave the queue up mid-run: pending, its work kept on disk."""
    with create_session_factory(engine)() as session:
        workspace = Workspace(name="w")
        session.add(workspace)
        session.flush()
        document = Document(
            workspace_id=workspace.id,
            title=name,
            document_type=DocumentType.FILE,
            status=DocumentStatus.PENDING,
            document_metadata={"mime_type": mime_type, "suffix": Path(name).suffix},
        )
        session.add(document)
        session.commit()
        folder = get_storage_settings().document_dir(workspace.id, document.id)
        return document.id, folder


def _write(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"work")


def _row(engine: Engine, document_id: int) -> Document:
    with create_session_factory(engine)() as session:
        document = session.get(Document, document_id)
        assert document is not None
        return document


def test_the_source_fails_with_the_reason_and_is_not_retried(
    engine: Engine, refused_pipeline: None
) -> None:
    """Failed, so the panel shows why and offers Retry; Huey is told not to."""
    document_id = _pending_note(engine, DocumentStatus.PENDING)

    with pytest.raises(CancelExecution) as cancelled:
        ingest_document.call_local(document_id)

    assert cancelled.value.retry is False
    document = _row(engine, document_id)
    assert document.status is DocumentStatus.FAILED
    assert document.error_message == f"ImportError: {REFUSED}"


def test_a_cancelled_source_stays_cancelled(
    engine: Engine, refused_pipeline: None
) -> None:
    """A cancel that landed while the job waited is not undone by the failure."""
    document_id = _pending_note(engine, DocumentStatus.CANCELLED)

    with pytest.raises(CancelExecution):
        ingest_document.call_local(document_id)

    assert _row(engine, document_id).status is DocumentStatus.CANCELLED


def test_a_parked_recording_drops_its_decoded_audio(
    engine: Engine, refused_pipeline: None
) -> None:
    """No run will come to clear it; what a retry resumes from stays."""
    document_id, folder = _parked_file(engine, "standup.ogg", "audio/ogg")
    files = work_files(folder)
    for path in (files.audio, files.progress, files.plan, files.windows):
        _write(path)

    with pytest.raises(CancelExecution):
        ingest_document.call_local(document_id)

    assert not files.audio.exists()
    assert not files.progress.exists()
    assert files.plan.exists()
    assert files.windows.exists()


def test_a_parked_reading_drops_its_batches(
    engine: Engine, refused_pipeline: None
) -> None:
    """Docling's batches and OCR's pages, as a cancel in the queue drops them."""
    document_id, folder = _parked_file(engine, "scan.pdf", "application/pdf")
    _write(batches_dir(folder) / "0001.json")
    _write(ocr_dir(folder) / "pages.json")

    with pytest.raises(CancelExecution):
        ingest_document.call_local(document_id)

    assert not batches_dir(folder).exists()
    assert not ocr_dir(folder).exists()


def test_the_write_lock_is_free_while_the_api_is_told(
    engine: Engine, refused_pipeline: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The notice is an HTTP call of up to 2 s; the API's own writes must not wait."""
    document_id = _pending_note(engine, DocumentStatus.PENDING)
    locked: list[bool] = []

    def tell_the_api(_document: Document) -> None:
        other = sqlite3.connect(get_storage_settings().database_path, timeout=0)
        try:
            other.execute("BEGIN IMMEDIATE")
            other.rollback()
            locked.append(False)
        except sqlite3.OperationalError:
            locked.append(True)
        finally:
            other.close()

    monkeypatch.setattr(
        "worker.unloadable_ingest.notify_document_updates", tell_the_api
    )

    with pytest.raises(CancelExecution):
        ingest_document.call_local(document_id)

    assert locked == [False]
