"""Create a converted PDF's artifact: version 1 of its own document, made by a Studio job."""

import logging

from sqlalchemy.orm import Session

from modules.artifacts.converted_documents.conversion import (
    CONVERSION_KEY,
    Conversion,
)
from modules.artifacts.converted_documents.input_file import (
    ConversionRefusedError,
    input_file,
)
from modules.artifacts.models import Artifact
from modules.artifacts.script_documents.version import ArtifactVersion
from modules.artifacts.tasks import studio_job
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.embedding.active import EmbeddingNotChosenError, require_active_index
from modules.workspaces.models import Workspace

logger = logging.getLogger(__name__)


def create_conversion(
    session: Session,
    workspace: Workspace,
    conversion: Conversion,
    *,
    chat_thread_id: int | None = None,
) -> Artifact:
    """Keep what to convert on a pending PDF artifact and queue Studio's job to convert it.

    A PDF is a document of its own, as the version switcher shows one format,
    so converting again makes another. Commits before enqueueing: the worker
    is another process and must find the row.
    """
    title, _ = input_file(session, workspace.id, conversion)
    # The job indexes the PDF's text; failing there would convert for nothing.
    try:
        require_active_index(session)
    except EmbeddingNotChosenError as error:
        raise ConversionRefusedError(
            "Studio is not ready on this computer: no embedding model is chosen yet."
        ) from error
    document = Document(
        workspace_id=workspace.id,
        title=title,
        document_type=DocumentType.ARTIFACT,
        status=DocumentStatus.PENDING,
    )
    session.add(document)
    session.flush()
    artifact = Artifact(
        document_id=document.id,
        workspace_id=workspace.id,
        format="pdf",
        chat_thread_id=chat_thread_id,
    )
    session.add(artifact)
    session.flush()
    artifact.artifact_metadata = {
        CONVERSION_KEY: conversion.as_metadata(),
        "version": ArtifactVersion(
            root=artifact.id, number=1, parent=None
        ).as_metadata(),
        "source_document_ids": (
            [conversion.document_id] if conversion.document_id is not None else []
        ),
        "prompt": None,
    }
    session.commit()
    studio_job(artifact.id)
    logger.info("studio: enqueued conversion %s to pdf", artifact.id)
    return artifact
