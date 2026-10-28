"""An ingest whose own code the OS will not load, as Windows' Smart App Control
refuses an unsigned native module (#2366): the source fails with the reason
instead of waiting for ever, and is not tried twice more to fail the same way."""

import sys
from collections.abc import Sequence
from importlib.abc import MetaPathFinder
from importlib.machinery import ModuleSpec
from types import ModuleType

import pytest
from huey.exceptions import CancelExecution
from sqlalchemy import Engine

from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.documents.tasks import ingest_document
from modules.workspaces.models import Workspace
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
