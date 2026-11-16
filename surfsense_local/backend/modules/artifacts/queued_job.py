"""Hand a Studio version to the worker once its row is written."""

from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.artifacts.tasks import studio_job
from modules.documents.models import DocumentStatus

QUEUE_FAILED = "This could not be queued. Retry it."


def queue_job(session: Session, artifact: Artifact) -> None:
    """Commit, then queue: the worker is another process and must find the row.

    A version whose job is not queued fails instead of staying pending, which
    nothing would end and which refuses every Retry and edit.
    """
    session.commit()
    try:
        studio_job(artifact.id)
    except Exception:
        session.rollback()
        artifact.document.status = DocumentStatus.FAILED
        artifact.document.error_message = QUEUE_FAILED
        session.commit()
        raise
