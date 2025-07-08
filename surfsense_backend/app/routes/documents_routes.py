from litellm import atranscription
from fastapi import APIRouter, Depends, BackgroundTasks, UploadFile, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from app.db import get_async_session, User, SearchSpace, Document, DocumentType
from app.schemas import DocumentsCreate, DocumentUpdate, DocumentRead
from app.users import current_active_user
from app.utils.check_ownership import check_ownership
from app.tasks.background_tasks import add_received_markdown_file_document, add_extension_received_document, add_received_file_document_using_unstructured, add_crawled_url_document, add_youtube_video_document, add_received_file_document_using_llamacloud
from app.config import config as app_config
# Force asyncio to use standard event loop before unstructured imports
import asyncio
try:
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
except RuntimeError:
    pass
import os
os.environ["UNSTRUCTURED_HAS_PATCHED_LOOP"] = "1"


router = APIRouter()


@router.post("/documents/")
async def create_documents(
    request: DocumentsCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
    fastapi_background_tasks: BackgroundTasks = BackgroundTasks()
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
                    str(user.id)
                )
        elif request.document_type == DocumentType.CRAWLED_URL:
            for url in request.content:
                fastapi_background_tasks.add_task(
                    process_crawled_url_with_new_session,
                    url,
                    request.search_space_id,
                    str(user.id)
                )
        elif request.document_type == DocumentType.YOUTUBE_VIDEO:
            for url in request.content:
                fastapi_background_tasks.add_task(
                    process_youtube_video_with_new_session,
                    url,
                    request.search_space_id,
                    str(user.id)
                )
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid document type"
            )

        await session.commit()
        return {"message": "Documents processed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process documents: {str(e)}"
        )


@router.post("/documents/fileupload")
async def create_documents(
    files: list[UploadFile],
    search_space_id: int = Form(...),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
    fastapi_background_tasks: BackgroundTasks = BackgroundTasks()
):
    try:
        await check_ownership(session, SearchSpace, search_space_id, user)

        if not files:
            raise HTTPException(status_code=400, detail="No files provided")

        for file in files:
            try:
                # Save file to a temporary location to avoid stream issues
                import tempfile
                import aiofiles
                import os

                # Create temp file
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
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
                    str(user.id)
                )
            except Exception as e:
                raise HTTPException(
                    status_code=422,
                    detail=f"Failed to process file {file.filename}: {str(e)}"
                )

        await session.commit()
        return {"message": "Files uploaded for processing"}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload files: {str(e)}"
        )


async def process_file_in_background(
    file_path: str,
    filename: str,
    search_space_id: int,
    user_id: str,
    session: AsyncSession
):
    try:
        # Check if the file is a markdown or text file
        if filename.lower().endswith(('.md', '.markdown', '.txt')):
            # For markdown files, read the content directly
            with open(file_path, 'r', encoding='utf-8') as f:
                markdown_content = f.read()

            # Clean up the temp file
            import os
            try:
                os.unlink(file_path)
            except:
                pass

            # Process markdown directly through specialized function
            await add_received_markdown_file_document(
                session,
                filename,
                markdown_content,
                search_space_id,
                user_id
            )
        # Check if the file is an audio file
        elif filename.lower().endswith(('.mp3', '.mp4', '.mpeg', '.mpga', '.m4a', '.wav', '.webm')):
            # Open the audio file for transcription
            with open(file_path, "rb") as audio_file:
                # Use LiteLLM for audio transcription
                if app_config.STT_SERVICE_API_BASE:
                    transcription_response = await atranscription(
                        model=app_config.STT_SERVICE,
                        file=audio_file,
                        api_base=app_config.STT_SERVICE_API_BASE,
                        api_key=app_config.STT_SERVICE_API_KEY
                    )
                else:
                    transcription_response = await atranscription(
                        model=app_config.STT_SERVICE,
                        api_key=app_config.STT_SERVICE_API_KEY,
                        file=audio_file
                    )

                # Extract the transcribed text
                transcribed_text = transcription_response.get("text", "")

                # Add metadata about the transcription
                transcribed_text = f"# Transcription of {filename}\n\n{transcribed_text}"

            # Clean up the temp file
            try:
                os.unlink(file_path)
            except:
                pass

            # Process transcription as markdown document
            await add_received_markdown_file_document(
                session,
                filename,
                transcribed_text,
                search_space_id,
                user_id
            )
        else:
            if app_config.ETL_SERVICE == "UNSTRUCTURED":
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

                # Clean up the temp file
                import os
                try:
                    os.unlink(file_path)
                except:
                    pass

                # Pass the documents to the existing background task
                await add_received_file_document_using_unstructured(
                    session,
                    filename,
                    docs,
                    search_space_id,
                    user_id
                )
            elif app_config.ETL_SERVICE == "LLAMACLOUD":
                from llama_cloud_services import LlamaParse
                from llama_cloud_services.parse.utils import ResultType

                
                # Create LlamaParse parser instance
                parser = LlamaParse(
                    api_key=app_config.LLAMA_CLOUD_API_KEY,
                    num_workers=1,  # Use single worker for file processing
                    verbose=True,
                    language="en",
                    result_type=ResultType.MD
                )
                
                # Parse the file asynchronously
                result = await parser.aparse(file_path)
                
                # Clean up the temp file
                import os
                try:
                    os.unlink(file_path)
                except:
                    pass
                
                # Get markdown documents from the result
                markdown_documents = await result.aget_markdown_documents(split_by_page=False)
                
                for doc in markdown_documents:
                    # Extract text content from the markdown documents
                    markdown_content = doc.text
                    
                    # Process the documents using our LlamaCloud background task
                    await add_received_file_document_using_llamacloud(
                        session,
                        filename,
                        llamacloud_markdown_document=markdown_content,
                        search_space_id=search_space_id,
                        user_id=user_id
                    )
    except Exception as e:
        import logging
        logging.error(f"Error processing file in background: {str(e)}")


@router.get("/documents/", response_model=List[DocumentRead])
async def read_documents(
    skip: int = 0,
    limit: int = 300,
    search_space_id: int = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    try:
        query = select(Document).join(SearchSpace).filter(
            SearchSpace.user_id == user.id)

        # Filter by search_space_id if provided
        if search_space_id is not None:
            query = query.filter(Document.search_space_id == search_space_id)

        result = await session.execute(
            query.offset(skip).limit(limit)
        )
        db_documents = result.scalars().all()

        # Convert database objects to API-friendly format
        api_documents = []
        for doc in db_documents:
            api_documents.append(DocumentRead(
                id=doc.id,
                title=doc.title,
                document_type=doc.document_type,
                document_metadata=doc.document_metadata,
                content=doc.content,
                created_at=doc.created_at,
                search_space_id=doc.search_space_id
            ))

        return api_documents
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch documents: {str(e)}"
        )


@router.get("/documents/{document_id}", response_model=DocumentRead)
async def read_document(
    document_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
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
                status_code=404,
                detail=f"Document with id {document_id} not found"
            )

        # Convert database object to API-friendly format
        return DocumentRead(
            id=document.id,
            title=document.title,
            document_type=document.document_type,
            document_metadata=document.document_metadata,
            content=document.content,
            created_at=document.created_at,
            search_space_id=document.search_space_id
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch document: {str(e)}"
        )


@router.put("/documents/{document_id}", response_model=DocumentRead)
async def update_document(
    document_id: int,
    document_update: DocumentUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
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
                status_code=404,
                detail=f"Document with id {document_id} not found"
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
            search_space_id=db_document.search_space_id
        )
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update document: {str(e)}"
        )


@router.delete("/documents/{document_id}", response_model=dict)
async def delete_document(
    document_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
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
                status_code=404,
                detail=f"Document with id {document_id} not found"
            )

        await session.delete(document)
        await session.commit()
        return {"message": "Document deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete document: {str(e)}"
        )


async def process_extension_document_with_new_session(
    individual_document,
    search_space_id: int,
    user_id: str
):
    """Create a new session and process extension document."""
    from app.db import async_session_maker

    async with async_session_maker() as session:
        try:
            await add_extension_received_document(session, individual_document, search_space_id, user_id)
        except Exception as e:
            import logging
            logging.error(f"Error processing extension document: {str(e)}")


async def process_crawled_url_with_new_session(
    url: str,
    search_space_id: int,
    user_id: str
):
    """Create a new session and process crawled URL."""
    from app.db import async_session_maker

    async with async_session_maker() as session:
        try:
            await add_crawled_url_document(session, url, search_space_id, user_id)
        except Exception as e:
            import logging
            logging.error(f"Error processing crawled URL: {str(e)}")


async def process_file_in_background_with_new_session(
    file_path: str,
    filename: str,
    search_space_id: int,
    user_id: str
):
    """Create a new session and process file."""
    from app.db import async_session_maker

    async with async_session_maker() as session:
        await process_file_in_background(file_path, filename, search_space_id, user_id, session)


async def process_youtube_video_with_new_session(
    url: str,
    search_space_id: int,
    user_id: str
):
    """Create a new session and process YouTube video."""
    from app.db import async_session_maker

    async with async_session_maker() as session:
        try:
            await add_youtube_video_document(session, url, search_space_id, user_id)
        except Exception as e:
            import logging
            logging.error(f"Error processing YouTube video: {str(e)}")


