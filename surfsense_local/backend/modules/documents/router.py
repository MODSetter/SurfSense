from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import select

from api.dependencies import SessionDep
from modules.documents.dependencies import DocumentDep
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.documents.schemas import (
    DocumentDetail,
    DocumentRead,
    DocumentUpdate,
    NoteCreate,
)
from modules.workspaces.dependencies import WorkspaceDep

router = APIRouter(prefix="/workspaces/{workspace_id}/documents", tags=["documents"])


@router.get(
    "",
    response_model=list[DocumentRead],
    summary="List a workspace's documents",
)
def list_documents(
    workspace: WorkspaceDep,
    session: SessionDep,
    document_type: Annotated[list[DocumentType] | None, Query()] = None,
    status_in: Annotated[list[DocumentStatus] | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Sequence[Document]:
    query = select(Document).where(Document.workspace_id == workspace.id)

    if document_type:
        query = query.where(Document.document_type.in_(document_type))
    if status_in:
        query = query.where(Document.status.in_(status_in))

    query = query.order_by(Document.created_at).limit(limit).offset(offset)

    return session.scalars(query).all()


@router.post(
    "",
    response_model=DocumentDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Write a note",
)
def create_note(
    payload: NoteCreate, workspace: WorkspaceDep, session: SessionDep
) -> Document:
    # A note arrives as text, so nothing needs parsing, but it stays pending
    # until the worker has chunked and indexed it: ready means searchable.
    note = Document(
        workspace_id=workspace.id,
        title=payload.title,
        document_type=DocumentType.NOTE,
        content=payload.content,
    )
    session.add(note)
    session.flush()
    return note


@router.get(
    "/{document_id}",
    response_model=DocumentDetail,
    summary="Read a document",
)
def read_document(document: DocumentDep) -> Document:
    return document


@router.patch(
    "/{document_id}",
    response_model=DocumentDetail,
    summary="Edit a document",
)
def update_document(document: DocumentDep, payload: DocumentUpdate) -> Document:
    if payload.title is not None:
        document.title = payload.title

    if payload.content is not None:
        if document.document_type is not DocumentType.NOTE:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "only a note's content is editable; the rest is extracted from a file",
            )
        document.content = payload.content
        # The indexed copy is now stale, and search would keep returning the
        # old text until the worker rebuilds it.
        document.status = DocumentStatus.PENDING

    return document


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document",
)
def delete_document(document: DocumentDep, session: SessionDep) -> Response:
    # Chunks cascade in the database. Notes own nothing else, but from phase two
    # an uploaded document also owns data/.../documents/{id}/ on disk and rows in
    # chunks_fts and chunk_vectors, and neither is reached by a foreign key.
    session.delete(document)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
