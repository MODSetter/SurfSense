from typing import NamedTuple

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.folders.models import Folder
from modules.folders.tree import subtree_ids


class FolderCancel(NamedTuple):
    cancelled: list[int]
    # (workspace id, document id) of each file cancelled while it waited: no run
    # is left to clear what a long reading that gave way kept.
    in_queue: list[tuple[int, int]]


def cancel_folder(session: Session, folder: Folder) -> FolderCancel:
    """Stop every queued or running read below a folder, in one UPDATE.

    No task is revoked one by one: a queued job finds its row cancelled at
    `begin_job` and does nothing, and a running one stops at its next check.
    """
    below = subtree_ids(session, [folder.id])
    waiting = session.execute(
        select(Document.id, Document.workspace_id).where(
            Document.folder_id.in_(below),
            Document.status == DocumentStatus.PENDING,
            Document.document_type == DocumentType.FILE,
        )
    ).all()
    cancelled = session.scalars(
        update(Document)
        .where(
            Document.folder_id.in_(below),
            Document.status.in_((DocumentStatus.PENDING, DocumentStatus.PROCESSING)),
        )
        .values(status=DocumentStatus.CANCELLED, error_message=None)
        .returning(Document.id)
    ).all()
    ended = set(cancelled)
    return FolderCancel(
        list(cancelled),
        [(workspace_id, id_) for id_, workspace_id in waiting if id_ in ended],
    )
