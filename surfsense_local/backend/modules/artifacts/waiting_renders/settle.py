"""Queue a waiting document once its pictures are drawn, or fail it when one is not.

Run where a picture's job ends, when a waiting document is made, and when the
worker starts, since a picture can end while no worker is running.
"""

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from modules.artifacts.drawn_images.names import image_name
from modules.artifacts.models import Artifact
from modules.artifacts.queued_job import queue_job
from modules.artifacts.waiting_renders.waits import KEY, waits_for
from modules.documents.models import Document, DocumentStatus, DocumentType

_ENDED_BADLY = (DocumentStatus.FAILED, DocumentStatus.CANCELLED)


def settle_waiting_renders(
    session: Session, *, picture_id: int | None = None, render_id: int | None = None
) -> list[Artifact]:
    """The waiting documents this settled, queued or failed, for the caller to announce."""
    settled: list[Artifact] = []
    for render in _waiting(session, picture_id, render_id):
        pictures = waits_for(render.artifact_metadata)
        statuses = _statuses(session, pictures)
        gone = [
            i
            for i in pictures
            if statuses.get(i) is None or statuses[i] in _ENDED_BADLY
        ]
        if gone:
            _fail(session, render, gone[0], statuses.get(gone[0]))
            settled.append(render)
        elif all(statuses[i] is DocumentStatus.READY for i in pictures) and _claim(
            session, render
        ):
            queue_job(session, render)
            settled.append(render)
    session.commit()
    return settled


def _waiting(
    session: Session, picture_id: int | None, render_id: int | None
) -> list[Artifact]:
    query = (
        select(Artifact)
        .join(Document, Artifact.document_id == Document.id)
        .where(
            Document.status == DocumentStatus.PENDING,
            Document.document_type == DocumentType.ARTIFACT,
            func.json_extract(Artifact.artifact_metadata, f"$.{KEY}").is_not(None),
        )
    )
    if render_id is not None:
        query = query.where(Artifact.id == render_id)
    found = session.scalars(query).all()
    if picture_id is None:
        return list(found)
    return [r for r in found if picture_id in waits_for(r.artifact_metadata)]


def _statuses(
    session: Session, artifact_ids: tuple[int, ...]
) -> dict[int, DocumentStatus]:
    rows = session.execute(
        select(Artifact.id, Document.status)
        .join(Document, Artifact.document_id == Document.id)
        .where(Artifact.id.in_(artifact_ids))
    )
    return dict(rows.tuples().all())


def _claim(session: Session, render: Artifact) -> bool:
    """Take the wait off in one update, so two pictures ending at once queue it once."""
    meta = {k: v for k, v in (render.artifact_metadata or {}).items() if k != KEY}
    claimed = session.execute(
        update(Artifact)
        .where(
            Artifact.id == render.id,
            func.json_extract(Artifact.artifact_metadata, f"$.{KEY}").is_not(None),
        )
        .values(artifact_metadata=meta)
        .execution_options(synchronize_session=False)
    )
    session.expire(render)
    return claimed.rowcount == 1


def _fail(
    session: Session, render: Artifact, picture_id: int, status: DocumentStatus | None
) -> None:
    name = image_name(picture_id)
    what = "was deleted" if status is None else "failed"
    render.document.status = DocumentStatus.FAILED
    render.document.error_message = (
        f"{name} {what}, so this document was not made. Draw that picture again, "
        "or render without it."
    )
