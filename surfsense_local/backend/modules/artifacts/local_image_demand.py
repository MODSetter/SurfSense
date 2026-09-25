"""Which model type Studio needs sd-server for now, so Electron runs it only
then: the weights stay resident until the process exits."""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.artifacts.formats import FORMATS, Format
from modules.artifacts.models import Artifact
from modules.documents.models import Document, DocumentStatus
from modules.llm.model_type import ModelType

# Ollama keeps a model this long after its last request; long enough that a
# second image does not reload one, short enough to give the memory back.
IDLE = timedelta(minutes=5)

# The types sd.cpp runs.
_LOCAL_IMAGE_TYPES = (ModelType.IMAGE_GEN, ModelType.IMAGE_EDIT, ModelType.VIDEO_GEN)
_ENDED = (DocumentStatus.READY, DocumentStatus.FAILED, DocumentStatus.CANCELLED)


def local_image_demand(session: Session, now: datetime) -> ModelType | None:
    """The oldest running job's image type; else the last one's, for IDLE after
    it ended; else None. A cancel ends the window at once: sd-server cannot
    stop a generation, so stopping the process is the cancel."""
    needs = {fmt.key: slot for fmt in FORMATS if (slot := _image_type(fmt))}
    jobs = (
        select(Artifact.format, Document.status, Document.updated_at)
        .join(Document, Artifact.document_id == Document.id)
        .where(Artifact.format.in_(needs))
    )
    running = session.execute(
        jobs.where(Document.status == DocumentStatus.PROCESSING)
        .order_by(Document.updated_at)
        .limit(1)
    ).first()
    if running is not None:
        return needs[running.format]
    last = session.execute(
        jobs.where(Document.status.in_(_ENDED))
        .order_by(Document.updated_at.desc())
        .limit(1)
    ).first()
    if last is None or last.status is DocumentStatus.CANCELLED:
        return None
    return needs[last.format] if now - last.updated_at < IDLE else None


def _image_type(fmt: Format) -> ModelType | None:
    return next((t for t in fmt.requires_model_types if t in _LOCAL_IMAGE_TYPES), None)
