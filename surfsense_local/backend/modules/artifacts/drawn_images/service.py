"""Create a picture the agent asked for: v1 of its own document, painted from its prompt alone."""

import logging

from sqlalchemy.orm import Session

from modules.artifacts.drawn_images.model import require_image_model
from modules.artifacts.drawn_images.recipe import image_drawn
from modules.artifacts.models import Artifact
from modules.artifacts.queued_job import queue_job
from modules.artifacts.studio_documents.recipe import RECIPE_KEY
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.embedding.active import require_active_index

logger = logging.getLogger(__name__)


def create_drawn_image(
    session: Session,
    workspace_id: int,
    *,
    title: str,
    prompt: str,
    format: str,
    chat_thread_id: int | None,
) -> Artifact:
    """Pending until Studio's job paints it. Commits before enqueueing: the worker
    is another process and must find the row."""
    require_image_model(session)
    # The job indexes the picture; failing there would spend the model call.
    require_active_index(session)
    document = Document(
        workspace_id=workspace_id,
        title=title,
        document_type=DocumentType.ARTIFACT,
        status=DocumentStatus.PENDING,
    )
    session.add(document)
    session.flush()
    artifact = Artifact(
        document_id=document.id,
        workspace_id=workspace_id,
        format=format,
        chat_thread_id=chat_thread_id,
        artifact_metadata={
            RECIPE_KEY: image_drawn(prompt),
            "source_document_ids": [],
            "prompt": prompt,
        },
    )
    session.add(artifact)
    session.flush()
    queue_job(session, artifact)
    logger.info("studio: enqueued drawn image %s format=%s", artifact.id, format)
    return artifact
