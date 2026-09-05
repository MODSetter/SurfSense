"""The worker as its own process, on the queue and database the API writes to."""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from sqlalchemy import Engine, text

from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.documents.tasks import ingest_document
from modules.workspaces.models import Workspace
from shared.db import create_db_engine, create_session_factory
from shared.migrations import upgrade_to_head
from shared.queue import huey

pytestmark = pytest.mark.integration

BACKEND = Path(__file__).resolve().parents[3]
# The queue opens its file at import, so the worker has to be handed the same
# data directory conftest set before anything else was imported.
DATA_DIR = Path(os.environ["SURFSENSE_LOCAL_DATA_DIR"])
# The model fetch_embedding_model.py downloaded; the subprocess cannot be monkeypatched.
REAL_MODELS = Path.home() / ".surfsense" / "models"

NOTE = "# Cassini\n\nThe orbiter reached Saturn in 2004.\n"


def wait_for(engine: Engine, document_id: int) -> DocumentStatus:
    """Block until the other process has finished with the document."""
    deadline = time.monotonic() + 120

    while time.monotonic() < deadline:
        with create_session_factory(engine)() as session:
            status = session.get(Document, document_id, populate_existing=True).status
            if status in (DocumentStatus.READY, DocumentStatus.FAILED):
                return status
        time.sleep(0.1)

    raise AssertionError("the worker never picked the job up")


def test_the_worker_ingests_a_job_the_api_enqueued() -> None:
    """Upload to searchable, across two processes that share only files."""
    if not (REAL_MODELS / "bge-small-en-v1.5" / "model_optimized.onnx").is_file():
        pytest.skip("run scripts/fetch_embedding_model.py to exercise the real encoder")

    engine = create_db_engine(DATA_DIR / "surfsense.db")
    upgrade_to_head(engine)

    with create_session_factory(engine)() as session:
        workspace = Workspace(name="Saturn")
        session.add(workspace)
        session.flush()
        note = Document(
            workspace_id=workspace.id,
            title="Cassini",
            document_type=DocumentType.NOTE,
            content=NOTE,
        )
        session.add(note)
        session.commit()
        document_id = note.id

    ingest_document(document_id)
    assert huey.pending_count() == 1, "the two processes share one queue file"

    worker = subprocess.Popen(
        [sys.executable, "worker.py"],
        cwd=BACKEND,
        env={**os.environ, "SURFSENSE_LOCAL_MODELS_DIR": str(REAL_MODELS)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        status = wait_for(engine, document_id)
    finally:
        worker.terminate()
        worker.wait(timeout=10)

    assert status is DocumentStatus.READY

    with create_session_factory(engine)() as session:
        indexed = session.scalar(
            text("SELECT count(*) FROM chunks WHERE document_id = :id"),
            {"id": document_id},
        )
        searchable = session.scalar(
            text("SELECT count(*) FROM chunks_fts WHERE chunks_fts MATCH 'Saturn'")
        )

    assert indexed == 1
    assert searchable == 1
