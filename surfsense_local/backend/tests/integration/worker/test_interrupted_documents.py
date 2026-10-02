"""A job the app quit in the middle of: its worker is gone, and so is its job.

Huey takes a job off the queue as it starts it, so nothing would ever finish
the document, and Retry accepts only a failed or cancelled one.
"""

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.workspaces.models import Workspace
from shared.db import create_session_factory
from worker.interrupted_documents import fail_interrupted_documents

pytestmark = pytest.mark.integration


def _documents(session: Session) -> dict[str, Document]:
    workspace = Workspace(name="w")
    session.add(workspace)
    session.flush()
    rows = {
        "parsing note": (DocumentType.NOTE, DocumentStatus.PROCESSING),
        "parsing file": (DocumentType.FILE, DocumentStatus.PROCESSING),
        "queued note": (DocumentType.NOTE, DocumentStatus.PENDING),
        "generating artifact": (DocumentType.ARTIFACT, DocumentStatus.PROCESSING),
    }
    documents = {
        title: Document(
            workspace_id=workspace.id, title=title, document_type=kind, status=status
        )
        for title, (kind, status) in rows.items()
    }
    session.add_all(documents.values())
    session.commit()
    return documents


def test_the_ingest_worker_fails_the_sources_it_left_half_done(engine: Engine) -> None:
    """Failed with a reason, so the sources panel offers Retry."""
    with create_session_factory(engine)() as session:
        documents = _documents(session)

        fail_interrupted_documents({DocumentType.FILE, DocumentType.NOTE})

        session.expire_all()
        for title in ("parsing note", "parsing file"):
            assert documents[title].status is DocumentStatus.FAILED
            assert documents[title].error_message == "interrupted when the app closed"


def test_a_queued_source_and_another_workers_job_are_left_alone(
    engine: Engine,
) -> None:
    """A queued job is still in the queue; an artifact is the Studio worker's."""
    with create_session_factory(engine)() as session:
        documents = _documents(session)

        fail_interrupted_documents({DocumentType.FILE, DocumentType.NOTE})

        session.expire_all()
        assert documents["queued note"].status is DocumentStatus.PENDING
        assert documents["generating artifact"].status is DocumentStatus.PROCESSING
