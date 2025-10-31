# Force asyncio to use standard event loop before unstructured imports
import asyncio

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db import (
    Chunk,
    Document,
    DocumentType,
    SearchSpace,
    User,
    get_async_session,
)
from app.schemas import (
    DocumentRead,
    DocumentsCreate,
    DocumentUpdate,
    DocumentWithChunksRead,
    PaginatedResponse,
)
from app.users import current_active_user
from app.utils.check_ownership import check_ownership

try:
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
except RuntimeError as e:
    print("Error setting event loop policy", e)
    pass

import os

os.environ["UNSTRUCTURED_HAS_PATCHED_LOOP"] = "1"


router = APIRouter()


@router.post("/documents")
async def create_documents(
    request: DocumentsCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    try:
        # Check if the user owns the search space
        await check_ownership(session, SearchSpace, request.search_space_id, user)

        if request.document_type == DocumentType.EXTENSION:
            from app.tasks.celery_tasks.document_tasks import (
                process_extension_document_task,
            )

            for individual_document in request.content:
                # Convert document to dict for Celery serialization
                document_dict = {
                    "metadata": {
                        "VisitedWebPageTitle": individual_document.metadata.VisitedWebPageTitle,
                        "VisitedWebPageURL": individual_document.metadata.VisitedWebPageURL,
                    },
                    "content": individual_document.content,
                }
                process_extension_document_task.delay(
                    document_dict, request.search_space_id, str(user.id)
                )
        elif request.document_type == DocumentType.CRAWLED_URL:
            from app.tasks.celery_tasks.document_tasks import process_crawled_url_task

            for url in request.content:
                process_crawled_url_task.delay(
                    url, request.search_space_id, str(user.id)
                )
        elif request.document_type == DocumentType.YOUTUBE_VIDEO:
            from app.tasks.celery_tasks.document_tasks import process_youtube_video_task

            for url in request.content:
                process_youtube_video_task.delay(
                    url, request.search_space_id, str(user.id)
                )
        else:
            raise HTTPException(status_code=400, detail="Invalid document type")

        await session.commit()
        return {"message": "Documents processed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to process documents: {e!s}"
        ) from e


@router.post("/documents/fileupload")
async def create_documents_file_upload(
    files: list[UploadFile],
    search_space_id: int = Form(...),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    try:
        await check_ownership(session, SearchSpace, search_space_id, user)

        if not files:
            raise HTTPException(status_code=400, detail="No files provided")

        for file in files:
            try:
                # Save file to a temporary location to avoid stream issues
                import os
                import tempfile

                # Create temp file
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=os.path.splitext(file.filename)[1]
                ) as temp_file:
                    temp_path = temp_file.name

                # Write uploaded file to temp file
                content = await file.read()
                with open(temp_path, "wb") as f:
                    f.write(content)

                from app.tasks.celery_tasks.document_tasks import (
                    process_file_upload_task,
                )

                process_file_upload_task.delay(
                    temp_path, file.filename, search_space_id, str(user.id)
                )
            except Exception as e:
                raise HTTPException(
                    status_code=422,
                    detail=f"Failed to process file {file.filename}: {e!s}",
                ) from e

        await session.commit()
        return {"message": "Files uploaded for processing"}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to upload files: {e!s}"
        ) from e


@router.get("/documents", response_model=PaginatedResponse[DocumentRead])
async def read_documents(
    skip: int | None = None,
    page: int | None = None,
    page_size: int = 50,
    search_space_id: int | None = None,
    document_types: str | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    List documents owned by the current user, with optional filtering and pagination.

    Args:
        skip: Absolute number of items to skip from the beginning. If provided, it takes precedence over 'page'.
        page: Zero-based page index used when 'skip' is not provided.
        page_size: Number of items per page (default: 50). Use -1 to return all remaining items after the offset.
        search_space_id: If provided, restrict results to a specific search space.
        document_types: Comma-separated list of document types to filter by (e.g., "EXTENSION,FILE,SLACK_CONNECTOR").
        session: Database session (injected).
        user: Current authenticated user (injected).

    Returns:
        PaginatedResponse[DocumentRead]: Paginated list of documents visible to the user.

    Notes:
        - If both 'skip' and 'page' are provided, 'skip' is used.
        - Results are scoped to documents owned by the current user.
    """
    try:
        from sqlalchemy import func

        query = (
            select(Document).join(SearchSpace).filter(SearchSpace.user_id == user.id)
        )

        # Filter by search_space_id if provided
        if search_space_id is not None:
            query = query.filter(Document.search_space_id == search_space_id)

        # Filter by document_types if provided
        if document_types is not None and document_types.strip():
            type_list = [t.strip() for t in document_types.split(",") if t.strip()]
            if type_list:
                query = query.filter(Document.document_type.in_(type_list))

        # Get total count
        count_query = (
            select(func.count())
            .select_from(Document)
            .join(SearchSpace)
            .filter(SearchSpace.user_id == user.id)
        )
        if search_space_id is not None:
            count_query = count_query.filter(
                Document.search_space_id == search_space_id
            )
        if document_types is not None and document_types.strip():
            type_list = [t.strip() for t in document_types.split(",") if t.strip()]
            if type_list:
                count_query = count_query.filter(Document.document_type.in_(type_list))
        total_result = await session.execute(count_query)
        total = total_result.scalar() or 0

        # Calculate offset
        offset = 0
        if skip is not None:
            offset = skip
        elif page is not None:
            offset = page * page_size

        # Get paginated results
        if page_size == -1:
            result = await session.execute(query.offset(offset))
        else:
            result = await session.execute(query.offset(offset).limit(page_size))

        db_documents = result.scalars().all()

        # Convert database objects to API-friendly format
        api_documents = []
        for doc in db_documents:
            api_documents.append(
                DocumentRead(
                    id=doc.id,
                    title=doc.title,
                    document_type=doc.document_type,
                    document_metadata=doc.document_metadata,
                    content=doc.content,
                    created_at=doc.created_at,
                    search_space_id=doc.search_space_id,
                )
            )

        return PaginatedResponse(items=api_documents, total=total)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch documents: {e!s}"
        ) from e


@router.get("/documents/search", response_model=PaginatedResponse[DocumentRead])
async def search_documents(
    title: str,
    skip: int | None = None,
    page: int | None = None,
    page_size: int = 50,
    search_space_id: int | None = None,
    document_types: str | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Search documents by title substring, optionally filtered by search_space_id and document_types.

    Args:
        title: Case-insensitive substring to match against document titles. Required.
        skip: Absolute number of items to skip from the beginning. If provided, it takes precedence over 'page'. Default: None.
        page: Zero-based page index used when 'skip' is not provided. Default: None.
        page_size: Number of items per page. Use -1 to return all remaining items after the offset. Default: 50.
        search_space_id: Filter results to a specific search space. Default: None.
        document_types: Comma-separated list of document types to filter by (e.g., "EXTENSION,FILE,SLACK_CONNECTOR").
        session: Database session (injected).
        user: Current authenticated user (injected).

    Returns:
        PaginatedResponse[DocumentRead]: Paginated list of documents matching the query and filter.

    Notes:
        - Title matching uses ILIKE (case-insensitive).
        - If both 'skip' and 'page' are provided, 'skip' is used.
    """
    try:
        from sqlalchemy import func

        query = (
            select(Document).join(SearchSpace).filter(SearchSpace.user_id == user.id)
        )
        if search_space_id is not None:
            query = query.filter(Document.search_space_id == search_space_id)

        # Only search by title (case-insensitive)
        query = query.filter(Document.title.ilike(f"%{title}%"))

        # Filter by document_types if provided
        if document_types is not None and document_types.strip():
            type_list = [t.strip() for t in document_types.split(",") if t.strip()]
            if type_list:
                query = query.filter(Document.document_type.in_(type_list))

        # Get total count
        count_query = (
            select(func.count())
            .select_from(Document)
            .join(SearchSpace)
            .filter(SearchSpace.user_id == user.id)
        )
        if search_space_id is not None:
            count_query = count_query.filter(
                Document.search_space_id == search_space_id
            )
        count_query = count_query.filter(Document.title.ilike(f"%{title}%"))
        if document_types is not None and document_types.strip():
            type_list = [t.strip() for t in document_types.split(",") if t.strip()]
            if type_list:
                count_query = count_query.filter(Document.document_type.in_(type_list))
        total_result = await session.execute(count_query)
        total = total_result.scalar() or 0

        # Calculate offset
        offset = 0
        if skip is not None:
            offset = skip
        elif page is not None:
            offset = page * page_size

        # Get paginated results
        if page_size == -1:
            result = await session.execute(query.offset(offset))
        else:
            result = await session.execute(query.offset(offset).limit(page_size))

        db_documents = result.scalars().all()

        # Convert database objects to API-friendly format
        api_documents = []
        for doc in db_documents:
            api_documents.append(
                DocumentRead(
                    id=doc.id,
                    title=doc.title,
                    document_type=doc.document_type,
                    document_metadata=doc.document_metadata,
                    content=doc.content,
                    created_at=doc.created_at,
                    search_space_id=doc.search_space_id,
                )
            )

        return PaginatedResponse(items=api_documents, total=total)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to search documents: {e!s}"
        ) from e


@router.get("/documents/type-counts")
async def get_document_type_counts(
    search_space_id: int | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Get counts of documents by type for the current user.

    Args:
        search_space_id: If provided, restrict counts to a specific search space.
        session: Database session (injected).
        user: Current authenticated user (injected).

    Returns:
        Dict mapping document types to their counts.
    """
    try:
        from sqlalchemy import func

        query = (
            select(Document.document_type, func.count(Document.id))
            .join(SearchSpace)
            .filter(SearchSpace.user_id == user.id)
            .group_by(Document.document_type)
        )

        if search_space_id is not None:
            query = query.filter(Document.search_space_id == search_space_id)

        result = await session.execute(query)
        type_counts = dict(result.all())

        return type_counts
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch document type counts: {e!s}"
        ) from e


@router.get("/documents/by-chunk/{chunk_id}", response_model=DocumentWithChunksRead)
async def get_document_by_chunk_id(
    chunk_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Retrieves a document based on a chunk ID, including all its chunks ordered by creation time.
    The document's embedding and chunk embeddings are excluded from the response.
    """
    try:
        # First, get the chunk and verify it exists
        chunk_result = await session.execute(select(Chunk).filter(Chunk.id == chunk_id))
        chunk = chunk_result.scalars().first()

        if not chunk:
            raise HTTPException(
                status_code=404, detail=f"Chunk with id {chunk_id} not found"
            )

        # Get the associated document and verify ownership
        document_result = await session.execute(
            select(Document)
            .options(selectinload(Document.chunks))
            .join(SearchSpace)
            .filter(Document.id == chunk.document_id, SearchSpace.user_id == user.id)
        )
        document = document_result.scalars().first()

        if not document:
            raise HTTPException(
                status_code=404,
                detail="Document not found or you don't have access to it",
            )

        # Sort chunks by creation time
        sorted_chunks = sorted(document.chunks, key=lambda x: x.created_at)

        # Return the document with its chunks
        return DocumentWithChunksRead(
            id=document.id,
            title=document.title,
            document_type=document.document_type,
            document_metadata=document.document_metadata,
            content=document.content,
            created_at=document.created_at,
            search_space_id=document.search_space_id,
            chunks=sorted_chunks,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve document: {e!s}"
        ) from e


@router.get("/documents/{document_id}", response_model=DocumentRead)
async def read_document(
    document_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    try:
        result = await session.execute(
            select(Document)
            .join(SearchSpace)
            .filter(Document.id == document_id, SearchSpace.user_id == user.id)
        )
        document = result.scalars().first()

        if not document:
            raise HTTPException(
                status_code=404, detail=f"Document with id {document_id} not found"
            )

        # Convert database object to API-friendly format
        return DocumentRead(
            id=document.id,
            title=document.title,
            document_type=document.document_type,
            document_metadata=document.document_metadata,
            content=document.content,
            created_at=document.created_at,
            search_space_id=document.search_space_id,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch document: {e!s}"
        ) from e


@router.put("/documents/{document_id}", response_model=DocumentRead)
async def update_document(
    document_id: int,
    document_update: DocumentUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    try:
        # Query the document directly instead of using read_document function
        result = await session.execute(
            select(Document)
            .join(SearchSpace)
            .filter(Document.id == document_id, SearchSpace.user_id == user.id)
        )
        db_document = result.scalars().first()

        if not db_document:
            raise HTTPException(
                status_code=404, detail=f"Document with id {document_id} not found"
            )

        update_data = document_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_document, key, value)
        await session.commit()
        await session.refresh(db_document)

        # Convert to DocumentRead for response
        return DocumentRead(
            id=db_document.id,
            title=db_document.title,
            document_type=db_document.document_type,
            document_metadata=db_document.document_metadata,
            content=db_document.content,
            created_at=db_document.created_at,
            search_space_id=db_document.search_space_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to update document: {e!s}"
        ) from e


@router.delete("/documents/{document_id}", response_model=dict)
async def delete_document(
    document_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    try:
        # Query the document directly instead of using read_document function
        result = await session.execute(
            select(Document)
            .join(SearchSpace)
            .filter(Document.id == document_id, SearchSpace.user_id == user.id)
        )
        document = result.scalars().first()

        if not document:
            raise HTTPException(
                status_code=404, detail=f"Document with id {document_id} not found"
            )

        await session.delete(document)
        await session.commit()
        return {"message": "Document deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to delete document: {e!s}"
        ) from e
