# Force asyncio to use standard event loop before unstructured imports
import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile
from litellm import atranscription
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.config import config as app_config
from app.db import (
    Chunk,
    Document,
    DocumentType,
    Log,
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
from app.services.task_logging_service import TaskLoggingService
from app.tasks.document_processors import (
    add_crawled_url_document,
    add_extension_received_document,
    add_received_file_document_using_docling,
    add_received_file_document_using_llamacloud,
    add_received_file_document_using_unstructured,
    add_received_markdown_file_document,
    add_youtube_video_document,
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


@router.post("/documents/")
async def create_documents(
    request: DocumentsCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
    fastapi_background_tasks: BackgroundTasks = BackgroundTasks(),
):
    try:
        # Check if the user owns the search space
        await check_ownership(session, SearchSpace, request.search_space_id, user)

        if request.document_type == DocumentType.EXTENSION:
            for individual_document in request.content:
                fastapi_background_tasks.add_task(
                    process_extension_document_with_new_session,
                    individual_document,
                    request.search_space_id,
                    str(user.id),
                )
        elif request.document_type == DocumentType.CRAWLED_URL:
            for url in request.content:
                fastapi_background_tasks.add_task(
                    process_crawled_url_with_new_session,
                    url,
                    request.search_space_id,
                    str(user.id),
                )
        elif request.document_type == DocumentType.YOUTUBE_VIDEO:
            for url in request.content:
                fastapi_background_tasks.add_task(
                    process_youtube_video_with_new_session,
                    url,
                    request.search_space_id,
                    str(user.id),
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
    fastapi_background_tasks: BackgroundTasks = BackgroundTasks(),
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

                fastapi_background_tasks.add_task(
                    process_file_in_background_with_new_session,
                    temp_path,
                    file.filename,
                    search_space_id,
                    str(user.id),
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


@router.get("/documents/", response_model=PaginatedResponse[DocumentRead])
async def read_documents(
    skip: int | None = None,
    page: int | None = None,
    page_size: int = 50,
    search_space_id: int | None = None,
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


@router.get("/documents/search/", response_model=PaginatedResponse[DocumentRead])
async def search_documents(
    title: str,
    skip: int | None = None,
    page: int | None = None,
    page_size: int = 50,
    search_space_id: int | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Search documents by title substring, optionally filtered by search_space_id.

    Args:
        title: Case-insensitive substring to match against document titles. Required.
        skip: Absolute number of items to skip from the beginning. If provided, it takes precedence over 'page'. Default: None.
        page: Zero-based page index used when 'skip' is not provided. Default: None.
        page_size: Number of items per page. Use -1 to return all remaining items after the offset. Default: 50.
        search_space_id: Filter results to a specific search space. Default: None.
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


async def process_extension_document_with_new_session(
    individual_document, search_space_id: int, user_id: str
):
    """Create a new session and process extension document."""
    from app.db import async_session_maker
    from app.services.task_logging_service import TaskLoggingService

    async with async_session_maker() as session:
        # Initialize task logging service
        task_logger = TaskLoggingService(session, search_space_id)

        # Log task start
        log_entry = await task_logger.log_task_start(
            task_name="process_extension_document",
            source="document_processor",
            message=f"Starting processing of extension document from {individual_document.metadata.VisitedWebPageTitle}",
            metadata={
                "document_type": "EXTENSION",
                "url": individual_document.metadata.VisitedWebPageURL,
                "title": individual_document.metadata.VisitedWebPageTitle,
                "user_id": user_id,
            },
        )

        try:
            result = await add_extension_received_document(
                session, individual_document, search_space_id, user_id
            )

            if result:
                await task_logger.log_task_success(
                    log_entry,
                    f"Successfully processed extension document: {individual_document.metadata.VisitedWebPageTitle}",
                    {"document_id": result.id, "content_hash": result.content_hash},
                )
            else:
                await task_logger.log_task_success(
                    log_entry,
                    f"Extension document already exists (duplicate): {individual_document.metadata.VisitedWebPageTitle}",
                    {"duplicate_detected": True},
                )
        except Exception as e:
            await task_logger.log_task_failure(
                log_entry,
                f"Failed to process extension document: {individual_document.metadata.VisitedWebPageTitle}",
                str(e),
                {"error_type": type(e).__name__},
            )
            import logging

            logging.error(f"Error processing extension document: {e!s}")


async def process_crawled_url_with_new_session(
    url: str, search_space_id: int, user_id: str
):
    """Create a new session and process crawled URL."""
    from app.db import async_session_maker
    from app.services.task_logging_service import TaskLoggingService

    async with async_session_maker() as session:
        # Initialize task logging service
        task_logger = TaskLoggingService(session, search_space_id)

        # Log task start
        log_entry = await task_logger.log_task_start(
            task_name="process_crawled_url",
            source="document_processor",
            message=f"Starting URL crawling and processing for: {url}",
            metadata={"document_type": "CRAWLED_URL", "url": url, "user_id": user_id},
        )

        try:
            result = await add_crawled_url_document(
                session, url, search_space_id, user_id
            )

            if result:
                await task_logger.log_task_success(
                    log_entry,
                    f"Successfully crawled and processed URL: {url}",
                    {
                        "document_id": result.id,
                        "title": result.title,
                        "content_hash": result.content_hash,
                    },
                )
            else:
                await task_logger.log_task_success(
                    log_entry,
                    f"URL document already exists (duplicate): {url}",
                    {"duplicate_detected": True},
                )
        except Exception as e:
            await task_logger.log_task_failure(
                log_entry,
                f"Failed to crawl URL: {url}",
                str(e),
                {"error_type": type(e).__name__},
            )
            import logging

            logging.error(f"Error processing crawled URL: {e!s}")


async def process_file_in_background_with_new_session(
    file_path: str, filename: str, search_space_id: int, user_id: str
):
    """Create a new session and process file."""
    from app.db import async_session_maker
    from app.services.task_logging_service import TaskLoggingService

    async with async_session_maker() as session:
        # Initialize task logging service
        task_logger = TaskLoggingService(session, search_space_id)

        # Log task start
        log_entry = await task_logger.log_task_start(
            task_name="process_file_upload",
            source="document_processor",
            message=f"Starting file processing for: {filename}",
            metadata={
                "document_type": "FILE",
                "filename": filename,
                "file_path": file_path,
                "user_id": user_id,
            },
        )

        try:
            await process_file_in_background(
                file_path,
                filename,
                search_space_id,
                user_id,
                session,
                task_logger,
                log_entry,
            )

            # Note: success/failure logging is handled within process_file_in_background
        except Exception as e:
            await task_logger.log_task_failure(
                log_entry,
                f"Failed to process file: {filename}",
                str(e),
                {"error_type": type(e).__name__},
            )
            import logging

            logging.error(f"Error processing file: {e!s}")


async def process_youtube_video_with_new_session(
    url: str, search_space_id: int, user_id: str
):
    """Create a new session and process YouTube video."""
    from app.db import async_session_maker
    from app.services.task_logging_service import TaskLoggingService

    async with async_session_maker() as session:
        # Initialize task logging service
        task_logger = TaskLoggingService(session, search_space_id)

        # Log task start
        log_entry = await task_logger.log_task_start(
            task_name="process_youtube_video",
            source="document_processor",
            message=f"Starting YouTube video processing for: {url}",
            metadata={"document_type": "YOUTUBE_VIDEO", "url": url, "user_id": user_id},
        )

        try:
            result = await add_youtube_video_document(
                session, url, search_space_id, user_id
            )

            if result:
                await task_logger.log_task_success(
                    log_entry,
                    f"Successfully processed YouTube video: {result.title}",
                    {
                        "document_id": result.id,
                        "video_id": result.document_metadata.get("video_id"),
                        "content_hash": result.content_hash,
                    },
                )
            else:
                await task_logger.log_task_success(
                    log_entry,
                    f"YouTube video document already exists (duplicate): {url}",
                    {"duplicate_detected": True},
                )
        except Exception as e:
            await task_logger.log_task_failure(
                log_entry,
                f"Failed to process YouTube video: {url}",
                str(e),
                {"error_type": type(e).__name__},
            )
            import logging

            logging.error(f"Error processing YouTube video: {e!s}")


async def process_file_in_background(
    file_path: str,
    filename: str,
    search_space_id: int,
    user_id: str,
    session: AsyncSession,
    task_logger: TaskLoggingService,
    log_entry: Log,
):
    try:
        # Check if the file is a markdown or text file
        if filename.lower().endswith((".md", ".markdown", ".txt")):
            await task_logger.log_task_progress(
                log_entry,
                f"Processing markdown/text file: {filename}",
                {"file_type": "markdown", "processing_stage": "reading_file"},
            )

            # For markdown files, read the content directly
            with open(file_path, encoding="utf-8") as f:
                markdown_content = f.read()

            # Clean up the temp file
            import os

            try:
                os.unlink(file_path)
            except Exception as e:
                print("Error deleting temp file", e)
                pass

            await task_logger.log_task_progress(
                log_entry,
                f"Creating document from markdown content: {filename}",
                {
                    "processing_stage": "creating_document",
                    "content_length": len(markdown_content),
                },
            )

            # Process markdown directly through specialized function
            result = await add_received_markdown_file_document(
                session, filename, markdown_content, search_space_id, user_id
            )

            if result:
                await task_logger.log_task_success(
                    log_entry,
                    f"Successfully processed markdown file: {filename}",
                    {
                        "document_id": result.id,
                        "content_hash": result.content_hash,
                        "file_type": "markdown",
                    },
                )
            else:
                await task_logger.log_task_success(
                    log_entry,
                    f"Markdown file already exists (duplicate): {filename}",
                    {"duplicate_detected": True, "file_type": "markdown"},
                )

        # Check if the file is an audio file
        elif filename.lower().endswith(
            (".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm")
        ):
            await task_logger.log_task_progress(
                log_entry,
                f"Processing audio file for transcription: {filename}",
                {"file_type": "audio", "processing_stage": "starting_transcription"},
            )

            # Open the audio file for transcription
            with open(file_path, "rb") as audio_file:
                # Use LiteLLM for audio transcription
                if app_config.STT_SERVICE_API_BASE:
                    transcription_response = await atranscription(
                        model=app_config.STT_SERVICE,
                        file=audio_file,
                        api_base=app_config.STT_SERVICE_API_BASE,
                        api_key=app_config.STT_SERVICE_API_KEY,
                    )
                else:
                    transcription_response = await atranscription(
                        model=app_config.STT_SERVICE,
                        api_key=app_config.STT_SERVICE_API_KEY,
                        file=audio_file,
                    )

                # Extract the transcribed text
                transcribed_text = transcription_response.get("text", "")

                # Add metadata about the transcription
                transcribed_text = (
                    f"# Transcription of {filename}\n\n{transcribed_text}"
                )

            await task_logger.log_task_progress(
                log_entry,
                f"Transcription completed, creating document: {filename}",
                {
                    "processing_stage": "transcription_complete",
                    "transcript_length": len(transcribed_text),
                },
            )

            # Clean up the temp file
            try:
                os.unlink(file_path)
            except Exception as e:
                print("Error deleting temp file", e)
                pass

            # Process transcription as markdown document
            result = await add_received_markdown_file_document(
                session, filename, transcribed_text, search_space_id, user_id
            )

            if result:
                await task_logger.log_task_success(
                    log_entry,
                    f"Successfully transcribed and processed audio file: {filename}",
                    {
                        "document_id": result.id,
                        "content_hash": result.content_hash,
                        "file_type": "audio",
                        "transcript_length": len(transcribed_text),
                    },
                )
            else:
                await task_logger.log_task_success(
                    log_entry,
                    f"Audio file transcript already exists (duplicate): {filename}",
                    {"duplicate_detected": True, "file_type": "audio"},
                )

        else:
            if app_config.ETL_SERVICE == "UNSTRUCTURED":
                await task_logger.log_task_progress(
                    log_entry,
                    f"Processing file with Unstructured ETL: {filename}",
                    {
                        "file_type": "document",
                        "etl_service": "UNSTRUCTURED",
                        "processing_stage": "loading",
                    },
                )

                from langchain_unstructured import UnstructuredLoader

                # Process the file
                loader = UnstructuredLoader(
                    file_path,
                    mode="elements",
                    post_processors=[],
                    languages=["eng"],
                    include_orig_elements=False,
                    include_metadata=False,
                    strategy="auto",
                )

                docs = await loader.aload()

                await task_logger.log_task_progress(
                    log_entry,
                    f"Unstructured ETL completed, creating document: {filename}",
                    {"processing_stage": "etl_complete", "elements_count": len(docs)},
                )

                # Clean up the temp file
                import os

                try:
                    os.unlink(file_path)
                except Exception as e:
                    print("Error deleting temp file", e)
                    pass

                # Pass the documents to the existing background task
                result = await add_received_file_document_using_unstructured(
                    session, filename, docs, search_space_id, user_id
                )

                if result:
                    await task_logger.log_task_success(
                        log_entry,
                        f"Successfully processed file with Unstructured: {filename}",
                        {
                            "document_id": result.id,
                            "content_hash": result.content_hash,
                            "file_type": "document",
                            "etl_service": "UNSTRUCTURED",
                        },
                    )
                else:
                    await task_logger.log_task_success(
                        log_entry,
                        f"Document already exists (duplicate): {filename}",
                        {
                            "duplicate_detected": True,
                            "file_type": "document",
                            "etl_service": "UNSTRUCTURED",
                        },
                    )

            elif app_config.ETL_SERVICE == "LLAMACLOUD":
                await task_logger.log_task_progress(
                    log_entry,
                    f"Processing file with LlamaCloud ETL: {filename}",
                    {
                        "file_type": "document",
                        "etl_service": "LLAMACLOUD",
                        "processing_stage": "parsing",
                    },
                )

                from llama_cloud_services import LlamaParse
                from llama_cloud_services.parse.utils import ResultType

                # Create LlamaParse parser instance
                parser = LlamaParse(
                    api_key=app_config.LLAMA_CLOUD_API_KEY,
                    num_workers=1,  # Use single worker for file processing
                    verbose=True,
                    language="en",
                    result_type=ResultType.MD,
                )

                # Parse the file asynchronously
                result = await parser.aparse(file_path)

                # Clean up the temp file
                import os

                try:
                    os.unlink(file_path)
                except Exception as e:
                    print("Error deleting temp file", e)
                    pass

                # Get markdown documents from the result
                markdown_documents = await result.aget_markdown_documents(
                    split_by_page=False
                )

                await task_logger.log_task_progress(
                    log_entry,
                    f"LlamaCloud parsing completed, creating documents: {filename}",
                    {
                        "processing_stage": "parsing_complete",
                        "documents_count": len(markdown_documents),
                    },
                )

                for doc in markdown_documents:
                    # Extract text content from the markdown documents
                    markdown_content = doc.text

                    # Process the documents using our LlamaCloud background task
                    doc_result = await add_received_file_document_using_llamacloud(
                        session,
                        filename,
                        llamacloud_markdown_document=markdown_content,
                        search_space_id=search_space_id,
                        user_id=user_id,
                    )

                if doc_result:
                    await task_logger.log_task_success(
                        log_entry,
                        f"Successfully processed file with LlamaCloud: {filename}",
                        {
                            "document_id": doc_result.id,
                            "content_hash": doc_result.content_hash,
                            "file_type": "document",
                            "etl_service": "LLAMACLOUD",
                        },
                    )
                else:
                    await task_logger.log_task_success(
                        log_entry,
                        f"Document already exists (duplicate): {filename}",
                        {
                            "duplicate_detected": True,
                            "file_type": "document",
                            "etl_service": "LLAMACLOUD",
                        },
                    )

            elif app_config.ETL_SERVICE == "DOCLING":
                await task_logger.log_task_progress(
                    log_entry,
                    f"Processing file with Docling ETL: {filename}",
                    {
                        "file_type": "document",
                        "etl_service": "DOCLING",
                        "processing_stage": "parsing",
                    },
                )

                # Use Docling service for document processing
                from app.services.docling_service import create_docling_service

                # Create Docling service
                docling_service = create_docling_service()

                # Process the document
                result = await docling_service.process_document(file_path, filename)

                # Clean up the temp file
                import os

                try:
                    os.unlink(file_path)
                except Exception as e:
                    print("Error deleting temp file", e)
                    pass

                await task_logger.log_task_progress(
                    log_entry,
                    f"Docling parsing completed, creating document: {filename}",
                    {
                        "processing_stage": "parsing_complete",
                        "content_length": len(result["content"]),
                    },
                )

                # Process the document using our Docling background task
                doc_result = await add_received_file_document_using_docling(
                    session,
                    filename,
                    docling_markdown_document=result["content"],
                    search_space_id=search_space_id,
                    user_id=user_id,
                )

                if doc_result:
                    await task_logger.log_task_success(
                        log_entry,
                        f"Successfully processed file with Docling: {filename}",
                        {
                            "document_id": doc_result.id,
                            "content_hash": doc_result.content_hash,
                            "file_type": "document",
                            "etl_service": "DOCLING",
                        },
                    )
                else:
                    await task_logger.log_task_success(
                        log_entry,
                        f"Document already exists (duplicate): {filename}",
                        {
                            "duplicate_detected": True,
                            "file_type": "document",
                            "etl_service": "DOCLING",
                        },
                    )
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to process file: {filename}",
            str(e),
            {"error_type": type(e).__name__, "filename": filename},
        )
        import logging

        logging.error(f"Error processing file in background: {e!s}")
        raise  # Re-raise so the wrapper can also handle it
