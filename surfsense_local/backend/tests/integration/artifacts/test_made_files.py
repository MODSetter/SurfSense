"""A file a tool made, kept as a new artifact: Studio's job only reads and indexes it."""

from pathlib import Path

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from modules.artifacts.made_file import (
    MadeFileRefusedError,
    keep_made_file,
    made_by,
)
from modules.artifacts.models import ArtifactFileRole
from modules.artifacts.service import regenerate_artifact
from modules.documents.models import DocumentStatus
from modules.workspaces.models import Workspace
from shared.config import get_storage_settings
from shared.db import create_session_factory
from tests.integration.worker.conftest import stub_model  # noqa: F401
from tests.unit.pdf_tools.pdfs import numbered
from worker.studio import run

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("stub_model")]

MADE_BY = {"tool": "pdf_pages", "operation": "extract", "pages": "1-2"}


def _keep(session: Session, workspace: Workspace, data: bytes | None = None):
    return keep_made_file(
        session,
        workspace.id,
        title="Board pack (pages 1-2)",
        format="pdf",
        data=data or numbered(2, "Board"),
        made_by=MADE_BY,
        document_ids=[11],
        artifact_ids=[4],
        chat_thread_id=None,
    )


def _primary_path(artifact) -> Path:
    (file,) = artifact.files
    return get_storage_settings().data_dir / file.storage_key


def test_the_file_is_kept_at_once_and_its_artifact_records_what_made_it(
    session: Session, workspace: Workspace
) -> None:
    """The artifact is usable before its job runs, and is a document of its own, not a version."""
    data = numbered(2, "Board")

    artifact = _keep(session, workspace, data)

    assert artifact.document.status is DocumentStatus.PENDING
    assert artifact.format == "pdf"
    (file,) = artifact.files
    assert file.role is ArtifactFileRole.PRIMARY
    assert file.mime_type == "application/pdf"
    assert file.original_filename == "Board pack (pages 1-2).pdf"
    assert _primary_path(artifact).read_bytes() == data
    assert made_by(artifact.artifact_metadata) == MADE_BY
    assert artifact.artifact_metadata["derived_from"] == {
        "document_ids": [11],
        "artifact_ids": [4],
    }
    assert artifact.artifact_metadata["source_document_ids"] == [11]
    assert "version" not in artifact.artifact_metadata


def test_studios_job_indexes_the_kept_file_without_changing_it(
    session: Session, workspace: Workspace
) -> None:
    """The job adds the searchable body (ADR-0003) and keeps the bytes the tool made."""
    data = numbered(2, "Board")
    artifact = _keep(session, workspace, data)

    run(artifact.id)

    session.expire_all()
    assert artifact.document.status is DocumentStatus.READY, (
        artifact.document.error_message
    )
    assert "Board 1" in artifact.document.content
    assert "Board 2" in artifact.document.content
    assert _primary_path(artifact).read_bytes() == data
    assert (
        session.scalar(
            text("SELECT count(*) FROM chunks_fts WHERE chunks_fts MATCH 'Board'")
        )
        == 1
    )


def test_regenerating_reads_the_file_again_and_asks_no_model(
    session: Session, workspace: Workspace
) -> None:
    """No chat model is chosen here; a draft's Regenerate would need one."""
    artifact = _keep(session, workspace)
    run(artifact.id)
    session.expire_all()

    regenerate_artifact(session, artifact)
    run(artifact.id)

    session.expire_all()
    assert artifact.document.status is DocumentStatus.READY
    assert artifact.generation == 2


def test_a_kept_file_that_does_not_open_fails_its_job_without_a_retry(
    session: Session, workspace: Workspace
) -> None:
    """Reading the same bytes again would fail the same way."""
    artifact = _keep(session, workspace, b"%PDF-1.7 cut short")

    run(artifact.id)  # returning, not raising, is what spares a Huey retry

    session.expire_all()
    assert artifact.document.status is DocumentStatus.FAILED
    assert artifact.document.error_message == ("The kept file does not open as a PDF.")


def test_a_file_is_not_kept_before_an_embedding_model_is_chosen(
    unlocked_engine: Engine,
) -> None:
    """The job could not index it, so nothing would find it."""
    with create_session_factory(unlocked_engine)() as session:
        workspace = Workspace(name="Fresh")
        session.add(workspace)
        session.commit()

        with pytest.raises(MadeFileRefusedError, match="no embedding model"):
            _keep(session, workspace)


def test_a_title_too_long_is_refused(session: Session, workspace: Workspace) -> None:
    """Studio's titles hold at most 200 characters."""
    with pytest.raises(MadeFileRefusedError, match="1 to 200 characters"):
        keep_made_file(
            session,
            workspace.id,
            title="x" * 201,
            format="pdf",
            data=numbered(1),
            made_by=MADE_BY,
            document_ids=[],
            artifact_ids=[],
            chat_thread_id=None,
        )
