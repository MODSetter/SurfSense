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
    Permission,
    SearchSpace,
    SearchSpaceMembership,
    User,
    get_async_session,
)
from app.schemas import (
    DocumentRead,
    DocumentsCreate,
    DocumentStatusBatchResponse,
    DocumentStatusItemRead,
    DocumentStatusSchema,
    DocumentTitleRead,
    DocumentTitleSearchResponse,
    DocumentUpdate,
    DocumentWithChunksRead,
    PaginatedResponse,
)
from app.users import current_active_user
from app.utils.rbac import check_permission

try:
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
except RuntimeError as e:
    print("Error setting event loop policy", e)
    pass

import os

os.environ["UNSTRUCTURED_HAS_PATCHED_LOOP"] = "1"


router = APIRouter()

MAX_FILES_PER_UPLOAD = 10
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB per file
MAX_TOTAL_SIZE_BYTES = 200 * 1024 * 1024  # 200 MB total


@router.post("/documents")
async def create_documents(
    request: DocumentsCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Create new documents.
    Requires DOCUMENTS_CREATE permission.
    """
    try:
        # Check permission
        await check_permission(
            session,
            user,
            request.search_space_id,
            Permission.DOCUMENTS_CREATE.value,
            "You don't have permission to create documents in this search space",
        )

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
                        "BrowsingSessionId": individual_document.metadata.BrowsingSessionId,
                        "VisitedWebPageDateWithTimeInISOString": individual_document.metadata.VisitedWebPageDateWithTimeInISOString,
                        "VisitedWebPageVisitDurationInMilliseconds": individual_document.metadata.VisitedWebPageVisitDurationInMilliseconds,
                        "VisitedWebPageReffererURL": individual_document.metadata.VisitedWebPageReffererURL,
                    },
                    "pageContent": individual_document.pageContent,
                }
                process_extension_document_task.delay(
                    document_dict, request.search_space_id, str(user.id)
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
        return {
            "message": "Documents queued for background processing",
            "status": "queued",
        }
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
    """
    Upload files as documents with real-time status tracking.

    Implements 2-phase document status updates for real-time UI feedback:
    - Phase 1: Create all documents with 'pending' status (visible in UI immediately via ElectricSQL)
    - Phase 2: Celery processes each file: pending → processing → ready/failed

    Requires DOCUMENTS_CREATE permission.
    """
    from datetime import datetime

    from app.db import DocumentStatus
    from app.tasks.document_processors.base import (
        check_document_by_unique_identifier,
        get_current_timestamp,
    )
    from app.utils.document_converters import generate_unique_identifier_hash

    try:
        # Check permission
        await check_permission(
            session,
            user,
            search_space_id,
            Permission.DOCUMENTS_CREATE.value,
            "You don't have permission to create documents in this search space",
        )

        if not files:
            raise HTTPException(status_code=400, detail="No files provided")

        if len(files) > MAX_FILES_PER_UPLOAD:
            raise HTTPException(
                status_code=413,
                detail=f"Too many files. Maximum {MAX_FILES_PER_UPLOAD} files per upload.",
            )

        total_size = 0
        for file in files:
            file_size = file.size or 0
            if file_size > MAX_FILE_SIZE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"File '{file.filename}' ({file_size / (1024 * 1024):.1f} MB) "
                    f"exceeds the {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB per-file limit.",
                )
            total_size += file_size

        if total_size > MAX_TOTAL_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Total upload size ({total_size / (1024 * 1024):.1f} MB) "
                f"exceeds the {MAX_TOTAL_SIZE_BYTES // (1024 * 1024)} MB limit.",
            )

        created_documents: list[Document] = []
        files_to_process: list[
            tuple[Document, str, str]
        ] = []  # (document, temp_path, filename)
        skipped_duplicates = 0
        duplicate_document_ids: list[int] = []
        actual_total_size = 0

        # ===== PHASE 1: Create pending documents for all files =====
        # This makes ALL documents visible in the UI immediately with pending status
        for file in files:
            try:
                import os
                import tempfile

                # Save file to temp location
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=os.path.splitext(file.filename or "")[1]
                ) as temp_file:
                    temp_path = temp_file.name

                content = await file.read()
                file_size = len(content)

                if file_size > MAX_FILE_SIZE_BYTES:
                    os.unlink(temp_path)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File '{file.filename}' ({file_size / (1024 * 1024):.1f} MB) "
                        f"exceeds the {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB per-file limit.",
                    )

                actual_total_size += file_size
                if actual_total_size > MAX_TOTAL_SIZE_BYTES:
                    os.unlink(temp_path)
                    raise HTTPException(
                        status_code=413,
                        detail=f"Total upload size ({actual_total_size / (1024 * 1024):.1f} MB) "
                        f"exceeds the {MAX_TOTAL_SIZE_BYTES // (1024 * 1024)} MB limit.",
                    )

                with open(temp_path, "wb") as f:
                    f.write(content)

                # Generate unique identifier for deduplication check
                unique_identifier_hash = generate_unique_identifier_hash(
                    DocumentType.FILE, file.filename or "unknown", search_space_id
                )

                # Check if document already exists (by unique identifier)
                existing = await check_document_by_unique_identifier(
                    session, unique_identifier_hash
                )
                if existing:
                    if DocumentStatus.is_state(existing.status, DocumentStatus.READY):
                        # True duplicate — content already indexed, skip
                        os.unlink(temp_path)
                        skipped_duplicates += 1
                        duplicate_document_ids.append(existing.id)
                        continue

                    # Existing document is stuck (failed/pending/processing)
                    # Reset it to pending and re-dispatch for processing
                    existing.status = DocumentStatus.pending()
                    existing.content = "Processing..."
                    existing.document_metadata = {
                        **(existing.document_metadata or {}),
                        "file_size": file_size,
                        "upload_time": datetime.now().isoformat(),
                    }
                    existing.updated_at = get_current_timestamp()
                    created_documents.append(existing)
                    files_to_process.append(
                        (existing, temp_path, file.filename or "unknown")
                    )
                    continue

                # Create pending document (visible immediately in UI via ElectricSQL)
                document = Document(
                    search_space_id=search_space_id,
                    title=file.filename or "Uploaded File",
                    document_type=DocumentType.FILE,
                    document_metadata={
                        "FILE_NAME": file.filename,
                        "file_size": file_size,
                        "upload_time": datetime.now().isoformat(),
                    },
                    content="Processing...",  # Placeholder until processed
                    content_hash=unique_identifier_hash,  # Temporary, updated when ready
                    unique_identifier_hash=unique_identifier_hash,
                    embedding=None,
                    status=DocumentStatus.pending(),  # Shows "pending" in UI
                    updated_at=get_current_timestamp(),
                    created_by_id=str(user.id),
                )
                session.add(document)
                created_documents.append(document)
                files_to_process.append(
                    (document, temp_path, file.filename or "unknown")
                )

            except Exception as e:
                raise HTTPException(
                    status_code=422,
                    detail=f"Failed to process file {file.filename}: {e!s}",
                ) from e

        # Commit all pending documents - they appear in UI immediately via ElectricSQL
        if created_documents:
            await session.commit()
            # Refresh to get generated IDs
            for doc in created_documents:
                await session.refresh(doc)

        # ===== PHASE 2: Dispatch Celery tasks for each file =====
        # Each task will update document status: pending → processing → ready/failed
        from app.tasks.celery_tasks.document_tasks import (
            process_file_upload_with_document_task,
        )

        for document, temp_path, filename in files_to_process:
            process_file_upload_with_document_task.delay(
                document_id=document.id,
                temp_path=temp_path,
                filename=filename,
                search_space_id=search_space_id,
                user_id=str(user.id),
            )

        return {
            "message": "Files uploaded for processing",
            "document_ids": [doc.id for doc in created_documents],
            "duplicate_document_ids": duplicate_document_ids,
            "total_files": len(files),
            "pending_files": len(files_to_process),
            "skipped_duplicates": skipped_duplicates,
        }
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
    List documents the user has access to, with optional filtering and pagination.
    Requires DOCUMENTS_READ permission for the search space(s).

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
        - Results are scoped to documents in search spaces the user has membership in.
    """
    try:
        from sqlalchemy import func

        # If specific search_space_id, check permission
        if search_space_id is not None:
            await check_permission(
                session,
                user,
                search_space_id,
                Permission.DOCUMENTS_READ.value,
                "You don't have permission to read documents in this search space",
            )
            query = (
                select(Document)
                .options(selectinload(Document.created_by))
                .filter(Document.search_space_id == search_space_id)
            )
            count_query = (
                select(func.count())
                .select_from(Document)
                .filter(Document.search_space_id == search_space_id)
            )
        else:
            # Get documents from all search spaces user has membership in
            query = (
                select(Document)
                .options(selectinload(Document.created_by))
                .join(SearchSpace)
                .join(SearchSpaceMembership)
                .filter(SearchSpaceMembership.user_id == user.id)
            )
            count_query = (
                select(func.count())
                .select_from(Document)
                .join(SearchSpace)
                .join(SearchSpaceMembership)
                .filter(SearchSpaceMembership.user_id == user.id)
            )

        # Filter by document_types if provided
        if document_types is not None and document_types.strip():
            type_list = [t.strip() for t in document_types.split(",") if t.strip()]
            if type_list:
                query = query.filter(Document.document_type.in_(type_list))
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
            created_by_name = None
            created_by_email = None
            if doc.created_by:
                created_by_name = doc.created_by.display_name
                created_by_email = doc.created_by.email

            # Parse status from JSONB
            status_data = None
            if hasattr(doc, "status") and doc.status:
                status_data = DocumentStatusSchema(
                    state=doc.status.get("state", "ready"),
                    reason=doc.status.get("reason"),
                )

            api_documents.append(
                DocumentRead(
                    id=doc.id,
                    title=doc.title,
                    document_type=doc.document_type,
                    document_metadata=doc.document_metadata,
                    content=doc.content,
                    content_hash=doc.content_hash,
                    unique_identifier_hash=doc.unique_identifier_hash,
                    created_at=doc.created_at,
                    updated_at=doc.updated_at,
                    search_space_id=doc.search_space_id,
                    created_by_id=doc.created_by_id,
                    created_by_name=created_by_name,
                    created_by_email=created_by_email,
                    status=status_data,
                )
            )

        # Calculate pagination info
        actual_page = (
            page if page is not None else (offset // page_size if page_size > 0 else 0)
        )
        has_more = (offset + len(api_documents)) < total if page_size > 0 else False

        return PaginatedResponse(
            items=api_documents,
            total=total,
            page=actual_page,
            page_size=page_size,
            has_more=has_more,
        )
    except HTTPException:
        raise
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
    Requires DOCUMENTS_READ permission for the search space(s).

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

        # If specific search_space_id, check permission
        if search_space_id is not None:
            await check_permission(
                session,
                user,
                search_space_id,
                Permission.DOCUMENTS_READ.value,
                "You don't have permission to read documents in this search space",
            )
            query = (
                select(Document)
                .options(selectinload(Document.created_by))
                .filter(Document.search_space_id == search_space_id)
            )
            count_query = (
                select(func.count())
                .select_from(Document)
                .filter(Document.search_space_id == search_space_id)
            )
        else:
            # Get documents from all search spaces user has membership in
            query = (
                select(Document)
                .options(selectinload(Document.created_by))
                .join(SearchSpace)
                .join(SearchSpaceMembership)
                .filter(SearchSpaceMembership.user_id == user.id)
            )
            count_query = (
                select(func.count())
                .select_from(Document)
                .join(SearchSpace)
                .join(SearchSpaceMembership)
                .filter(SearchSpaceMembership.user_id == user.id)
            )

        # Only search by title (case-insensitive)
        query = query.filter(Document.title.ilike(f"%{title}%"))
        count_query = count_query.filter(Document.title.ilike(f"%{title}%"))

        # Filter by document_types if provided
        if document_types is not None and document_types.strip():
            type_list = [t.strip() for t in document_types.split(",") if t.strip()]
            if type_list:
                query = query.filter(Document.document_type.in_(type_list))
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
            created_by_name = None
            created_by_email = None
            if doc.created_by:
                created_by_name = doc.created_by.display_name
                created_by_email = doc.created_by.email

            # Parse status from JSONB
            status_data = None
            if hasattr(doc, "status") and doc.status:
                status_data = DocumentStatusSchema(
                    state=doc.status.get("state", "ready"),
                    reason=doc.status.get("reason"),
                )

            api_documents.append(
                DocumentRead(
                    id=doc.id,
                    title=doc.title,
                    document_type=doc.document_type,
                    document_metadata=doc.document_metadata,
                    content=doc.content,
                    content_hash=doc.content_hash,
                    unique_identifier_hash=doc.unique_identifier_hash,
                    created_at=doc.created_at,
                    updated_at=doc.updated_at,
                    search_space_id=doc.search_space_id,
                    created_by_id=doc.created_by_id,
                    created_by_name=created_by_name,
                    created_by_email=created_by_email,
                    status=status_data,
                )
            )

        # Calculate pagination info
        actual_page = (
            page if page is not None else (offset // page_size if page_size > 0 else 0)
        )
        has_more = (offset + len(api_documents)) < total if page_size > 0 else False

        return PaginatedResponse(
            items=api_documents,
            total=total,
            page=actual_page,
            page_size=page_size,
            has_more=has_more,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to search documents: {e!s}"
        ) from e


@router.get("/documents/search/titles", response_model=DocumentTitleSearchResponse)
async def search_document_titles(
    search_space_id: int,
    title: str = "",
    page: int = 0,
    page_size: int = 20,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Lightweight document title search optimized for mention picker (@mentions).

    Returns only id, title, and document_type - no content or metadata.
    Uses pg_trgm fuzzy search with similarity scoring for typo tolerance.
    Results are ordered by relevance using trigram similarity scores.

    Args:
        search_space_id: The search space to search in. Required.
        title: Search query (case-insensitive). If empty or < 2 chars, returns recent documents.
        page: Zero-based page index. Default: 0.
        page_size: Number of items per page. Default: 20.
        session: Database session (injected).
        user: Current authenticated user (injected).

    Returns:
        DocumentTitleSearchResponse: Lightweight list with has_more flag (no total count).
    """
    from sqlalchemy import desc, func, or_

    try:
        # Check permission for the search space
        await check_permission(
            session,
            user,
            search_space_id,
            Permission.DOCUMENTS_READ.value,
            "You don't have permission to read documents in this search space",
        )

        # Base query - only select lightweight fields
        query = select(
            Document.id,
            Document.title,
            Document.document_type,
        ).filter(Document.search_space_id == search_space_id)

        # If query is too short, return recent documents ordered by updated_at
        if len(title.strip()) < 2:
            query = query.order_by(Document.updated_at.desc().nullslast())
        else:
            # Fuzzy search using pg_trgm similarity + ILIKE fallback
            search_term = title.strip()

            # Similarity threshold for fuzzy matching (0.3 = ~30% trigram overlap)
            # Lower values = more fuzzy, higher values = stricter matching
            similarity_threshold = 0.3

            # Match documents that either:
            # 1. Have high trigram similarity (fuzzy match - handles typos)
            # 2. Contain the exact substring (ILIKE - handles partial matches)
            query = query.filter(
                or_(
                    func.similarity(Document.title, search_term) > similarity_threshold,
                    Document.title.ilike(f"%{search_term}%"),
                )
            )

            # Order by similarity score (descending) for best relevance ranking
            # Higher similarity = better match = appears first
            query = query.order_by(
                desc(func.similarity(Document.title, search_term)),
                Document.title,  # Alphabetical tiebreaker
            )

        # Fetch page_size + 1 to determine has_more without COUNT query
        offset = page * page_size
        result = await session.execute(query.offset(offset).limit(page_size + 1))
        rows = result.all()

        # Check if there are more results
        has_more = len(rows) > page_size
        items = rows[:page_size]  # Only return requested page_size

        # Convert to response format
        api_documents = [
            DocumentTitleRead(
                id=row.id,
                title=row.title,
                document_type=row.document_type,
            )
            for row in items
        ]

        return DocumentTitleSearchResponse(
            items=api_documents,
            has_more=has_more,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to search document titles: {e!s}"
        ) from e


@router.get("/documents/status", response_model=DocumentStatusBatchResponse)
async def get_documents_status(
    search_space_id: int,
    document_ids: str,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Batch status endpoint for documents in a search space.

    Returns lightweight status info for the provided document IDs, intended for
    polling async ETL progress in chat upload flows.
    """
    try:
        await check_permission(
            session,
            user,
            search_space_id,
            Permission.DOCUMENTS_READ.value,
            "You don't have permission to read documents in this search space",
        )

        # Parse comma-separated IDs (e.g. "1,2,3")
        parsed_ids = []
        for raw_id in document_ids.split(","):
            value = raw_id.strip()
            if not value:
                continue
            try:
                parsed_ids.append(int(value))
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid document id: {value}",
                ) from None

        if not parsed_ids:
            return DocumentStatusBatchResponse(items=[])

        result = await session.execute(
            select(Document).filter(
                Document.search_space_id == search_space_id,
                Document.id.in_(parsed_ids),
            )
        )
        docs = result.scalars().all()

        items = [
            DocumentStatusItemRead(
                id=doc.id,
                title=doc.title,
                document_type=doc.document_type,
                status=DocumentStatusSchema(
                    state=(doc.status or {}).get("state", "ready"),
                    reason=(doc.status or {}).get("reason"),
                ),
            )
            for doc in docs
        ]
        return DocumentStatusBatchResponse(items=items)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch document status: {e!s}"
        ) from e


@router.get("/documents/type-counts")
async def get_document_type_counts(
    search_space_id: int | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Get counts of documents by type for search spaces the user has access to.
    Requires DOCUMENTS_READ permission for the search space(s).

    Args:
        search_space_id: If provided, restrict counts to a specific search space.
        session: Database session (injected).
        user: Current authenticated user (injected).

    Returns:
        Dict mapping document types to their counts.
    """
    try:
        from sqlalchemy import func

        if search_space_id is not None:
            # Check permission for specific search space
            await check_permission(
                session,
                user,
                search_space_id,
                Permission.DOCUMENTS_READ.value,
                "You don't have permission to read documents in this search space",
            )
            query = (
                select(Document.document_type, func.count(Document.id))
                .filter(Document.search_space_id == search_space_id)
                .group_by(Document.document_type)
            )
        else:
            # Get counts from all search spaces user has membership in
            query = (
                select(Document.document_type, func.count(Document.id))
                .join(SearchSpace)
                .join(SearchSpaceMembership)
                .filter(SearchSpaceMembership.user_id == user.id)
                .group_by(Document.document_type)
            )

        result = await session.execute(query)
        type_counts = dict(result.all())

        return type_counts
    except HTTPException:
        raise
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
    Requires DOCUMENTS_READ permission for the search space.
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

        # Get the associated document
        document_result = await session.execute(
            select(Document)
            .options(selectinload(Document.chunks))
            .filter(Document.id == chunk.document_id)
        )
        document = document_result.scalars().first()

        if not document:
            raise HTTPException(
                status_code=404,
                detail="Document not found",
            )

        # Check permission for the search space
        await check_permission(
            session,
            user,
            document.search_space_id,
            Permission.DOCUMENTS_READ.value,
            "You don't have permission to read documents in this search space",
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
            content_hash=document.content_hash,
            unique_identifier_hash=document.unique_identifier_hash,
            created_at=document.created_at,
            updated_at=document.updated_at,
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
    """
    Get a specific document by ID.
    Requires DOCUMENTS_READ permission for the search space.
    """
    try:
        result = await session.execute(
            select(Document).filter(Document.id == document_id)
        )
        document = result.scalars().first()

        if not document:
            raise HTTPException(
                status_code=404, detail=f"Document with id {document_id} not found"
            )

        # Check permission for the search space
        await check_permission(
            session,
            user,
            document.search_space_id,
            Permission.DOCUMENTS_READ.value,
            "You don't have permission to read documents in this search space",
        )

        # Convert database object to API-friendly format
        return DocumentRead(
            id=document.id,
            title=document.title,
            document_type=document.document_type,
            document_metadata=document.document_metadata,
            content=document.content,
            content_hash=document.content_hash,
            unique_identifier_hash=document.unique_identifier_hash,
            created_at=document.created_at,
            updated_at=document.updated_at,
            search_space_id=document.search_space_id,
        )
    except HTTPException:
        raise
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
    """
    Update a document.
    Requires DOCUMENTS_UPDATE permission for the search space.
    """
    try:
        result = await session.execute(
            select(Document).filter(Document.id == document_id)
        )
        db_document = result.scalars().first()

        if not db_document:
            raise HTTPException(
                status_code=404, detail=f"Document with id {document_id} not found"
            )

        # Check permission for the search space
        await check_permission(
            session,
            user,
            db_document.search_space_id,
            Permission.DOCUMENTS_UPDATE.value,
            "You don't have permission to update documents in this search space",
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
            content_hash=db_document.content_hash,
            unique_identifier_hash=db_document.unique_identifier_hash,
            created_at=db_document.created_at,
            updated_at=db_document.updated_at,
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
    """
    Delete a document.
    Requires DOCUMENTS_DELETE permission for the search space.
    Documents in "processing" state cannot be deleted.
    """
    try:
        result = await session.execute(
            select(Document).filter(Document.id == document_id)
        )
        document = result.scalars().first()

        if not document:
            raise HTTPException(
                status_code=404, detail=f"Document with id {document_id} not found"
            )

        # Check if document is pending or currently being processed
        doc_state = document.status.get("state") if document.status else None
        if doc_state in ("pending", "processing"):
            raise HTTPException(
                status_code=409,  # Conflict
                detail="Cannot delete document while it is pending or being processed. Please wait for processing to complete.",
            )

        # Check permission for the search space
        await check_permission(
            session,
            user,
            document.search_space_id,
            Permission.DOCUMENTS_DELETE.value,
            "You don't have permission to delete documents in this search space",
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
