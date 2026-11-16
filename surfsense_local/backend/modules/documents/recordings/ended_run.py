"""What a recording's work keeps once its job stops short of a transcript, a
cancel included: the plan and the windows written, which a retry carries on
from, but not the decoded audio, 115 MB an hour and seconds to make again."""

import logging

from modules.documents.models import Document, DocumentStatus
from modules.documents.recordings.kind import is_recording
from modules.documents.recordings.layout import WorkFiles, work_files
from shared.config import get_storage_settings

__all__ = ["drop_run_files", "drop_when_cancelled_in_queue"]

logger = logging.getLogger(__name__)


def drop_run_files(files: WorkFiles) -> None:
    """Best-effort: a file another process holds open on Windows stays."""
    for path in (files.audio, files.progress):
        try:
            path.unlink(missing_ok=True)
        except OSError as error:
            logger.info("transcription: %s stays: %s", path, error)


def drop_when_cancelled_in_queue(document: Document, was: DocumentStatus) -> None:
    """A recording that gave the queue up has no run left to clear its own; a
    running one clears them as it stops."""
    if was is DocumentStatus.PENDING and is_recording(document.mime_type):
        folder = get_storage_settings().document_dir(document.workspace_id, document.id)
        drop_run_files(work_files(folder))
