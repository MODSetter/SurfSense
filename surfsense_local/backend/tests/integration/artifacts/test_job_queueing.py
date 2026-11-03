"""A Studio version whose job cannot be queued fails, rather than staying
pending with no job to end it, which would refuse every Retry and edit."""

import pytest
from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.artifacts.schemas import StudioJobCreate
from modules.artifacts.service import create_artifact_job, regenerate_artifact
from modules.documents.models import Document, DocumentStatus
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from modules.workspaces.models import Workspace

pytestmark = pytest.mark.integration


class QueueLockedError(RuntimeError):
    pass


@pytest.fixture
def queue_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    """Queueing raises, as a locked or full queue file makes it."""

    def refuse(_artifact_id: int) -> None:
        raise QueueLockedError("database is locked")

    monkeypatch.setattr("modules.artifacts.queued_job.studio_job", refuse)


@pytest.fixture
def chat_model(session: Session) -> None:
    """What a summary needs to be offered at all."""
    session.add(
        SelectedModel(model_type=ModelType.TEXT_GEN, provider="llamacpp", name="m")
    )
    session.commit()


def _failed_with_a_reason(session: Session, artifact_id: int) -> None:
    session.expire_all()
    artifact = session.get(Artifact, artifact_id)
    assert artifact.document.status is DocumentStatus.FAILED
    assert artifact.document.error_message == "This could not be queued. Retry it."


def test_a_new_job_that_cannot_be_queued_fails(
    session: Session,
    workspace: Workspace,
    logo_source: Document,
    chat_model: None,
    queue_refuses: None,
) -> None:
    """The row is committed before the job is queued, so it would wait forever."""
    with pytest.raises(QueueLockedError):
        create_artifact_job(
            session,
            workspace,
            StudioJobCreate(format="summary", document_ids=[logo_source.id]),
        )

    (artifact_id,) = session.scalars(
        Artifact.__table__.select().with_only_columns(Artifact.id)
    )
    _failed_with_a_reason(session, artifact_id)


def test_a_retry_that_cannot_be_queued_fails_again(
    session: Session,
    workspace: Workspace,
    logo_source: Document,
    chat_model: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retry can then be pressed once more; a pending version refuses it."""
    monkeypatch.setattr("modules.artifacts.queued_job.studio_job", lambda _id: None)
    artifact = create_artifact_job(
        session,
        workspace,
        StudioJobCreate(format="summary", document_ids=[logo_source.id]),
    )
    artifact.document.status = DocumentStatus.FAILED
    session.commit()

    def refuse(_artifact_id: int) -> None:
        raise QueueLockedError("database is locked")

    monkeypatch.setattr("modules.artifacts.queued_job.studio_job", refuse)
    with pytest.raises(QueueLockedError):
        regenerate_artifact(session, artifact)

    _failed_with_a_reason(session, artifact.id)
