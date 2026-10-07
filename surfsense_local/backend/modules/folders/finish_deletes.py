import logging

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased, sessionmaker

from modules.folders.delete_folder import purge_deleting
from modules.folders.models import Folder, FolderState
from modules.folders.tree import subtree_ids

logger = logging.getLogger(__name__)


def finish_interrupted_deletes(session_factory: sessionmaker[Session]) -> None:
    """Finish the folder deletes a previous run stopped partway through."""
    parent = aliased(Folder)
    with session_factory() as session:
        tops = session.execute(
            select(Folder.id, Folder.workspace_id)
            .join(parent, Folder.parent_id == parent.id)
            .where(
                Folder.state == FolderState.DELETING,
                parent.state != FolderState.DELETING,
            )
        ).all()
        for folder_id, workspace_id in tops:
            folders = subtree_ids(session, [folder_id])
            deleted = purge_deleting(session, folder_id, workspace_id, folders)
            logger.info(
                "finished deleting folder %s: %s sources", folder_id, len(deleted)
            )
