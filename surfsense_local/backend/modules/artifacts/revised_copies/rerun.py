"""Make a version of a revised copy again: the same edits on the same input, asking no model."""

from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.artifacts.revised_copies.refusals import RevisedCopyRefusedError
from modules.artifacts.revised_copies.versions import IN_FLIGHT
from modules.artifacts.tasks import studio_job
from modules.documents.models import DocumentStatus


def rerun_revised_copy(session: Session, artifact: Artifact) -> Artifact:
    """Regenerate and Retry of a revised copy; unlike a Studio draft's, no source is gathered."""
    document = artifact.document
    if document.status in IN_FLIGHT:
        raise RevisedCopyRefusedError("already generating")
    document.status = DocumentStatus.PENDING
    document.error_message = None
    artifact.generation += 1
    session.commit()
    studio_job(artifact.id)
    return artifact
