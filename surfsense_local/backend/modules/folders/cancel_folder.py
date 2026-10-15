from sqlalchemy import update
from sqlalchemy.orm import Session

from modules.documents.models import Document, DocumentStatus
from modules.folders.models import Folder
from modules.folders.tree import subtree_ids


def cancel_folder(session: Session, folder: Folder) -> list[int]:
    """Stop every queued or running read below a folder, in one UPDATE.

    No task is revoked one by one: a queued job finds its row cancelled at
    `begin_job` and does nothing, and a running one stops at its next check.
    """
    cancelled = session.scalars(
        update(Document)
        .where(
            Document.folder_id.in_(subtree_ids(session, [folder.id])),
            Document.status.in_((DocumentStatus.PENDING, DocumentStatus.PROCESSING)),
        )
        .values(status=DocumentStatus.CANCELLED, error_message=None)
        .returning(Document.id)
    ).all()
    return list(cancelled)
