"""Create the next version an edit makes: pending, naming the version it starts from."""

import logging

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from modules.artifacts.comic.pages import COMIC_PAGE, is_comic_page
from modules.artifacts.image_edits.editable import EDITABLE_FORMATS, has_picture
from modules.artifacts.image_edits.recipe import image_edited
from modules.artifacts.models import Artifact
from modules.artifacts.queued_job import queue_job
from modules.artifacts.refused import refused
from modules.artifacts.script_documents.version import (
    ArtifactVersion,
    next_version_number,
    version_of,
)
from modules.artifacts.studio_documents.recipe import RECIPE_KEY
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.embedding.active import require_active_index

logger = logging.getLogger(__name__)

_BUSY = (DocumentStatus.PENDING, DocumentStatus.PROCESSING)


def editable_base(session: Session, artifact_id: int) -> Artifact:
    """The version an edit would start from, or the HTTP refusal saying why it cannot."""
    artifact = session.get(Artifact, artifact_id)
    if artifact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "artifact not found")
    # The job indexes the new version; failing there would spend the model call.
    require_active_index(session)
    if artifact.document.status in _BUSY:
        raise refused(
            status.HTTP_409_CONFLICT, "already generating", "already_generating"
        )
    if artifact.format not in EDITABLE_FORMATS:
        raise _not_editable()
    if artifact.document.status is not DocumentStatus.READY:
        raise refused(
            status.HTTP_409_CONFLICT,
            "This version did not finish: retry it, or edit another version.",
            "image_version_unfinished",
        )
    if not has_picture(artifact):
        raise _not_editable()
    return artifact


def _not_editable() -> HTTPException:
    return refused(
        status.HTTP_409_CONFLICT,
        "Only an image or infographic made in Studio can be edited.",
        "not_editable",
    )


def create_image_edit_version(
    session: Session, artifact_id: int, instruction: str
) -> Artifact:
    """The base's next version, pending until Studio's job edits its picture.

    An image drawn before versions were kept becomes v1 here. Commits before
    enqueueing: the worker is another process and must find the row. A version
    stays in its base's chat, whichever box asked, so that chat can still place it.
    """
    base = editable_base(session, artifact_id)
    base_version = version_of(base.artifact_metadata) or ArtifactVersion(
        root=base.id, number=1, parent=None
    )
    meta = base.artifact_metadata or {}
    if version_of(meta) is None:
        base.artifact_metadata = {**meta, "version": base_version.as_metadata()}

    document = Document(
        workspace_id=base.workspace_id,
        title=base.document.title,
        document_type=DocumentType.ARTIFACT,
        status=DocumentStatus.PENDING,
    )
    session.add(document)
    session.flush()
    artifact = Artifact(
        document_id=document.id,
        workspace_id=base.workspace_id,
        format=base.format,
        chat_thread_id=base.chat_thread_id,
    )
    session.add(artifact)
    session.flush()
    version = ArtifactVersion(
        root=base_version.root,
        number=next_version_number(session, base.workspace_id, base_version.root),
        parent=base.id,
    )
    artifact.artifact_metadata = {
        RECIPE_KEY: image_edited(instruction, base.id),
        "version": version.as_metadata(),
        "source_document_ids": list(meta.get("source_document_ids") or []),
        "prompt": meta.get("prompt"),
        # A comic's page changed is its page still.
        **({COMIC_PAGE: True} if is_comic_page(meta) else {}),
    }
    queue_job(session, artifact)
    logger.info(
        "studio: enqueued image edit %s of %s root=%s v%s",
        artifact.id,
        base.id,
        version.root,
        version.number,
    )
    return artifact
