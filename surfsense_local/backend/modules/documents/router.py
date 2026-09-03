import shutil
from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from api.dependencies import SessionDep
from modules.documents.dependencies import DocumentDep
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.documents.schemas import (
    DocumentDetail,
    DocumentRead,
    DocumentUpdate,
    DuplicateRead,
    NoteCreate,
    UploadOutcome,
)
from modules.documents.storage import StreamedUpload, stream_upload, suffix_of, title_of
from modules.documents.tasks import ingest_document
from modules.workspaces.dependencies import WorkspaceDep
from shared.config import get_storage_settings

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


@router.post(
    "/upload",
    response_model=UploadOutcome,
    status_code=status.HTTP_201_CREATED,
    summary="Upload files",
)
def upload_documents(
    files: list[UploadFile], workspace: WorkspaceDep, session: SessionDep
) -> UploadOutcome:
    storage = get_storage_settings()
    created: list[Document] = []
    duplicates: list[DuplicateRead] = []
    accepted: list[tuple[Document, StreamedUpload, str]] = []

    try:
        for upload in files:
            streamed = stream_upload(upload, storage.workspace_dir(workspace.id))

            # Keyed on the bytes: the same report under two names is one
            # document, and two unrelated files both called report.pdf are two.
            twin = session.scalar(
                select(Document).where(
                    Document.workspace_id == workspace.id,
                    Document.dedup_key == streamed.digest,
                )
            )
            if twin is not None:
                streamed.path.unlink(missing_ok=True)
                duplicates.append(
                    DuplicateRead(filename=title_of(upload), document_id=twin.id)
                )
                continue

            document = Document(
                workspace_id=workspace.id,
                title=title_of(upload),
                document_type=DocumentType.FILE,
                dedup_key=streamed.digest,
                document_metadata={
                    "mime_type": upload.content_type,
                    "size_bytes": streamed.size,
                    "suffix": suffix_of(upload),
                },
            )
            session.add(document)
            # The file is stored under the id the database is about to assign.
            session.flush()
            created.append(document)
            accepted.append((document, streamed, suffix_of(upload)))
    except BaseException:
        for _, streamed, _ in accepted:
            streamed.path.unlink(missing_ok=True)
        raise

    for document, streamed, suffix in accepted:
        destination = storage.document_dir(workspace.id, document.id)
        destination.mkdir(parents=True, exist_ok=True)
        streamed.path.replace(destination / f"original{suffix}")

    # Before enqueueing, not by the session dependency afterwards: the worker is
    # another process and would look for a row this request had not written yet.
    session.commit()

    for document, _, _ in accepted:
        ingest_document(document.id)

    return UploadOutcome(created=created, duplicates=duplicates)


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


@router.post(
    "/{document_id}/retry",
    response_model=DocumentDetail,
    summary="Requeue a failed document",
)
def retry_document(document: DocumentDep, session: SessionDep) -> Document:
    # Otherwise failed is terminal: the same bytes re-uploaded are a duplicate.
    if document.status is not DocumentStatus.FAILED:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "only a failed document can be retried"
        )

    document.status = DocumentStatus.PENDING
    document.error_message = None
    session.commit()

    ingest_document(document.id)
    return document


@router.get(
    "/{document_id}/original",
    response_class=FileResponse,
    summary="Download the uploaded file",
)
def read_original(document: DocumentDep) -> FileResponse:
    suffix = (document.document_metadata or {}).get("suffix", "")
    path = (
        get_storage_settings().document_dir(document.workspace_id, document.id)
        / f"original{suffix}"
    )

    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no file behind this document")

    # Never inline: a stored html or svg would run its script on this origin.
    return FileResponse(
        path,
        filename=document.title,
        media_type=(document.document_metadata or {}).get("mime_type")
        or "application/octet-stream",
        content_disposition_type="attachment",
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document",
)
def delete_document(document: DocumentDep, session: SessionDep) -> Response:
    # Chunks cascade and their triggers clear both indexes. Only the bytes are
    # beyond the database, and go after the commit a rollback would undo.
    directory = get_storage_settings().document_dir(document.workspace_id, document.id)

    session.delete(document)
    session.commit()

    shutil.rmtree(directory, ignore_errors=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
