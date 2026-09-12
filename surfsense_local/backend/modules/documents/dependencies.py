from typing import Annotated

from fastapi import Depends, HTTPException, status

from api.dependencies import SessionDep
from modules.documents.models import Document
from modules.workspaces.dependencies import WorkspaceDep


def get_document(
    document_id: int, workspace: WorkspaceDep, session: SessionDep
) -> Document:
    """Resolve a document within its workspace.

    Scoping the lookup to the workspace in the path keeps one workspace's id
    from reading another's document.
    """
    document = session.get(Document, document_id)
    if document is None or document.workspace_id != workspace.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")

    return document


DocumentDep = Annotated[Document, Depends(get_document)]
