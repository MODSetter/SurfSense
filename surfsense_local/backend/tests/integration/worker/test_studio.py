from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact, ArtifactFileRole
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.workspaces.models import Workspace
from shared.config import get_storage_settings
from shared.db import create_session_factory
from worker.studio import persist, run
from worker.studio.builders import Built

pytestmark = pytest.mark.integration

SUMMARY = "# Cassini\n\nThe orbiter reached Saturn in 2004, carrying Huygens."


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """A session on the migrated database the pipeline opens again by path."""
    with create_session_factory(engine)() as opened:
        yield opened


def make_artifact(session: Session, *, source: str = "Saturn facts.") -> Artifact:
    """A workspace with one ready source and a pending summary artifact over it."""
    workspace = Workspace(name="Saturn")
    session.add(workspace)
    session.flush()

    source_doc = Document(
        workspace_id=workspace.id,
        title="Facts",
        document_type=DocumentType.NOTE,
        status=DocumentStatus.READY,
        content=source,
    )
    session.add(source_doc)
    session.flush()

    document = Document(
        workspace_id=workspace.id,
        title="Summary",
        document_type=DocumentType.ARTIFACT,
        status=DocumentStatus.PENDING,
    )
    session.add(document)
    session.flush()

    artifact = Artifact(
        document_id=document.id,
        workspace_id=workspace.id,
        format="summary",
        artifact_metadata={"source_document_ids": [source_doc.id], "prompt": None},
    )
    session.add(artifact)
    session.commit()
    return artifact


def test_a_summary_becomes_ready_and_searchable(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The model's markdown becomes the artifact's body and is indexed like a source."""
    monkeypatch.setattr("worker.studio.generate.generate", lambda *a, **k: SUMMARY)
    artifact = make_artifact(session)

    run(artifact.id)

    session.expire_all()
    document = artifact.document
    assert document.status is DocumentStatus.READY
    assert document.title == "Cassini"
    assert document.content == SUMMARY

    keyword = session.scalar(
        text("SELECT count(*) FROM chunks_fts WHERE chunks_fts MATCH 'Huygens'")
    )
    assert keyword == 1


def test_a_generation_failure_leaves_a_reason(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A model or builder error fails the artifact's document with why."""

    def boom(*args: object, **kwargs: object) -> str:
        raise RuntimeError("the model refused")

    monkeypatch.setattr("worker.studio.generate.generate", boom)
    artifact = make_artifact(session)

    with pytest.raises(RuntimeError, match="refused"):
        run(artifact.id)

    session.expire_all()
    assert artifact.document.status is DocumentStatus.FAILED
    assert "refused" in (artifact.document.error_message or "")
    assert session.scalar(text("SELECT count(*) FROM chunks")) == 0


def test_persist_stores_a_primary_blob(session: Session, stub_model: None) -> None:
    """A file format's bytes land on disk with a row that resolves back to them."""
    artifact = make_artifact(session)
    built = Built(
        title="Deck",
        markdown="# Deck\n\nOne slide.",
        primary=b"%PDF-1.7 fake",
        primary_mime="application/pdf",
    )

    persist.persist(session, artifact, artifact.document, built)
    session.commit()

    session.expire_all()
    assert len(artifact.files) == 1
    stored = artifact.files[0]
    assert stored.role is ArtifactFileRole.PRIMARY
    assert stored.size_bytes == len(built.primary)

    path = get_storage_settings().data_dir / stored.storage_key
    assert path.read_bytes() == built.primary


def test_an_artifact_deleted_before_generation_is_not_an_error(
    engine: Engine, stub_model: None
) -> None:
    """The route commits before enqueueing; a user can delete in the gap."""
    run(9999)
