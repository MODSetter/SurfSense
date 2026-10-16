import logging
import os

import httpx

from modules.artifacts.models import Artifact
from modules.documents.models import Document
from modules.events.schemas import EventKind, Progress

logger = logging.getLogger(__name__)


def notify_document_updates(
    document: Document, progress: Progress | None = None
) -> None:
    """Tell the API a document's row changed, so it can push the change to the UI.
    `progress`: a recording's, once per transcribed window."""
    _notify(
        document.workspace_id,
        EventKind.DOCUMENTS,
        document.id,
        document.status.value,
        progress,
    )


def notify_artifact_updates(artifact: Artifact) -> None:
    """Tell the API an artifact's generation state changed (status is its document's)."""
    _notify(
        artifact.workspace_id,
        EventKind.ARTIFACTS,
        artifact.id,
        artifact.document.status.value,
    )


def _notify(
    workspace_id: int,
    kind: EventKind,
    row_id: int,
    status: str,
    progress: Progress | None = None,
) -> None:
    """Fire the loopback change notice, best-effort.

    Worker and API share the database, so a dropped notice costs the client only
    its live update until the next poll, never the job and never a Huey retry.
    Skipped when no API address is set (tests, a bare worker run).
    """
    port = os.environ.get("SURFSENSE_LOCAL_PORT")
    if not port:
        return

    host = os.environ.get("SURFSENSE_LOCAL_HOST", "127.0.0.1")
    notice: dict = {
        "workspace_id": workspace_id,
        "kind": kind.value,
        "ids": [row_id],
        "status": status,
    }
    if progress is not None:
        notice["progress"] = progress.model_dump()
    try:
        httpx.post(
            f"http://{host}:{port}/internal/events",
            json=notice,
            timeout=2.0,
        )
    except Exception as error:
        logger.warning(
            "could not notify the API of %s %s: %s", kind.value, row_id, error
        )
