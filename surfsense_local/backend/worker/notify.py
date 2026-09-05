import logging
import os

import httpx

from modules.documents.models import Document
from modules.events.schemas import EventKind

logger = logging.getLogger(__name__)


def notify_document_updates(document: Document) -> None:
    """Tell the API a document's row changed, so it can push the change to the UI.

    Best-effort: worker and API share the database, so a dropped notice costs the
    client only its live update until the next poll, never the ingest and never a
    Huey retry. Skipped when no API address is set (tests, a bare worker run).
    """
    port = os.environ.get("SURFSENSE_LOCAL_PORT")
    if not port:
        return

    host = os.environ.get("SURFSENSE_LOCAL_HOST", "127.0.0.1")
    try:
        httpx.post(
            f"http://{host}:{port}/internal/events",
            json={
                "workspace_id": document.workspace_id,
                "kind": EventKind.DOCUMENTS.value,
                "ids": [document.id],
                "status": document.status.value,
            },
            timeout=2.0,
        )
    except Exception as error:
        logger.warning("could not notify the API of document %s: %s", document.id, error)
