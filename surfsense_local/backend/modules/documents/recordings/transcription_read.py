"""A recording's transcription as its row reports it: the language heard, how
far a queued or running job has come, and whether it waits for a speech model."""

from pydantic import BaseModel

from modules.documents.models import Document, DocumentStatus
from modules.documents.recordings.kind import is_recording
from modules.documents.recordings.layout import work_files
from modules.documents.recordings.metadata import is_awaiting, transcription_entry
from modules.documents.recordings.progress_file import read_progress
from modules.events.schemas import Progress
from shared.config import get_storage_settings

__all__ = ["TranscriptionRead", "transcription_read"]

_UNDER_WAY = (DocumentStatus.PENDING, DocumentStatus.PROCESSING)


class TranscriptionRead(BaseModel):
    # The language most windows were heard in, once transcribed.
    language: str | None
    # A yielded recording is pending with part of it done.
    progress: Progress | None
    # It failed only for want of a speech model; choosing one queues it again.
    awaiting: bool


def transcription_read(document: Document) -> TranscriptionRead | None:
    """None for anything that is not a recording."""
    if not is_recording(document.mime_type):
        return None
    entry = transcription_entry(document.document_metadata)
    language = entry.get("language")
    return TranscriptionRead(
        language=language if isinstance(language, str) else None,
        progress=_progress(document) if document.status in _UNDER_WAY else None,
        awaiting=document.status is DocumentStatus.FAILED
        and is_awaiting(document.document_metadata),
    )


def _progress(document: Document) -> Progress | None:
    folder = get_storage_settings().document_dir(document.workspace_id, document.id)
    kept = read_progress(work_files(folder).progress)
    return None if kept is None else Progress(done_s=kept.done_s, total_s=kept.total_s)
