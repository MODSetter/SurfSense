"""
File document processors for different ETL services (Unstructured, LlamaCloud, Docling).
"""

import contextlib
import logging
import warnings
from logging import ERROR, getLogger

from fastapi import HTTPException
from langchain_core.documents import Document as LangChainDocument
from litellm import atranscription
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config as app_config
from app.db import Document, DocumentType, Log
from app.services.llm_service import get_user_long_context_llm
from app.services.task_logging_service import TaskLoggingService
from app.utils.document_converters import (
    convert_document_to_markdown,
    create_document_chunks,
    generate_content_hash,
    generate_document_summary,
    generate_unique_identifier_hash,
)

from .base import (
    check_document_by_unique_identifier,
)
from .markdown_processor import add_received_markdown_file_document


async def add_received_file_document_using_unstructured(
    session: AsyncSession,
    file_name: str,
    unstructured_processed_elements: list[LangChainDocument],
    search_space_id: int,
    user_id: str,
) -> Document | None:
    """
    Process and store a file document using Unstructured service.

    Args:
        session: Database session
        file_name: Name of the processed file
        unstructured_processed_elements: Processed elements from Unstructured
        search_space_id: ID of the search space
        user_id: ID of the user

    Returns:
        Document object if successful, None if failed
    """
    try:
        file_in_markdown = await convert_document_to_markdown(
            unstructured_processed_elements
        )

        # Generate unique identifier hash for this file
        unique_identifier_hash = generate_unique_identifier_hash(
            DocumentType.FILE, file_name, search_space_id
        )

        # Generate content hash
        content_hash = generate_content_hash(file_in_markdown, search_space_id)

        # Check if document with this unique identifier already exists
        existing_document = await check_document_by_unique_identifier(
            session, unique_identifier_hash
        )

        if existing_document:
            # Document exists - check if content has changed
            if existing_document.content_hash == content_hash:
                logging.info(f"Document for file {file_name} unchanged. Skipping.")
                return existing_document
            else:
                # Content has changed - update the existing document
                logging.info(
                    f"Content changed for file {file_name}. Updating document."
                )

        # Get user's long context LLM (needed for both create and update)
        user_llm = await get_user_long_context_llm(session, user_id, search_space_id)
        if not user_llm:
            raise RuntimeError(
                f"No long context LLM configured for user {user_id} in search space {search_space_id}"
            )

        # Generate summary with metadata
        document_metadata = {
            "file_name": file_name,
            "etl_service": "UNSTRUCTURED",
            "document_type": "File Document",
        }
        summary_content, summary_embedding = await generate_document_summary(
            file_in_markdown, user_llm, document_metadata
        )

        # Process chunks
        chunks = await create_document_chunks(file_in_markdown)

        # Update or create document
        if existing_document:
            # Update existing document
            existing_document.title = file_name
            existing_document.content = summary_content
            existing_document.content_hash = content_hash
            existing_document.embedding = summary_embedding
            existing_document.document_metadata = {
                "FILE_NAME": file_name,
                "ETL_SERVICE": "UNSTRUCTURED",
            }
            existing_document.chunks = chunks

            await session.commit()
            await session.refresh(existing_document)
            document = existing_document
        else:
            # Create new document
            document = Document(
                search_space_id=search_space_id,
                title=file_name,
                document_type=DocumentType.FILE,
                document_metadata={
                    "FILE_NAME": file_name,
                    "ETL_SERVICE": "UNSTRUCTURED",
                },
                content=summary_content,
                embedding=summary_embedding,
                chunks=chunks,
                content_hash=content_hash,
                unique_identifier_hash=unique_identifier_hash,
            )

            session.add(document)
            await session.commit()
            await session.refresh(document)

        return document
    except SQLAlchemyError as db_error:
        await session.rollback()
        raise db_error
    except Exception as e:
        await session.rollback()
        raise RuntimeError(f"Failed to process file document: {e!s}") from e


async def add_received_file_document_using_llamacloud(
    session: AsyncSession,
    file_name: str,
    llamacloud_markdown_document: str,
    search_space_id: int,
    user_id: str,
) -> Document | None:
    """
    Process and store document content parsed by LlamaCloud.

    Args:
        session: Database session
        file_name: Name of the processed file
        llamacloud_markdown_document: Markdown content from LlamaCloud parsing
        search_space_id: ID of the search space
        user_id: ID of the user

    Returns:
        Document object if successful, None if failed
    """
    try:
        # Combine all markdown documents into one
        file_in_markdown = llamacloud_markdown_document

        # Generate unique identifier hash for this file
        unique_identifier_hash = generate_unique_identifier_hash(
            DocumentType.FILE, file_name, search_space_id
        )

        # Generate content hash
        content_hash = generate_content_hash(file_in_markdown, search_space_id)

        # Check if document with this unique identifier already exists
        existing_document = await check_document_by_unique_identifier(
            session, unique_identifier_hash
        )

        if existing_document:
            # Document exists - check if content has changed
            if existing_document.content_hash == content_hash:
                logging.info(f"Document for file {file_name} unchanged. Skipping.")
                return existing_document
            else:
                # Content has changed - update the existing document
                logging.info(
                    f"Content changed for file {file_name}. Updating document."
                )

        # Get user's long context LLM (needed for both create and update)
        user_llm = await get_user_long_context_llm(session, user_id, search_space_id)
        if not user_llm:
            raise RuntimeError(
                f"No long context LLM configured for user {user_id} in search space {search_space_id}"
            )

        # Generate summary with metadata
        document_metadata = {
            "file_name": file_name,
            "etl_service": "LLAMACLOUD",
            "document_type": "File Document",
        }
        summary_content, summary_embedding = await generate_document_summary(
            file_in_markdown, user_llm, document_metadata
        )

        # Process chunks
        chunks = await create_document_chunks(file_in_markdown)

        # Update or create document
        if existing_document:
            # Update existing document
            existing_document.title = file_name
            existing_document.content = summary_content
            existing_document.content_hash = content_hash
            existing_document.embedding = summary_embedding
            existing_document.document_metadata = {
                "FILE_NAME": file_name,
                "ETL_SERVICE": "LLAMACLOUD",
            }
            existing_document.chunks = chunks

            await session.commit()
            await session.refresh(existing_document)
            document = existing_document
        else:
            # Create new document
            document = Document(
                search_space_id=search_space_id,
                title=file_name,
                document_type=DocumentType.FILE,
                document_metadata={
                    "FILE_NAME": file_name,
                    "ETL_SERVICE": "LLAMACLOUD",
                },
                content=summary_content,
                embedding=summary_embedding,
                chunks=chunks,
                content_hash=content_hash,
                unique_identifier_hash=unique_identifier_hash,
            )

            session.add(document)
            await session.commit()
            await session.refresh(document)

        return document
    except SQLAlchemyError as db_error:
        await session.rollback()
        raise db_error
    except Exception as e:
        await session.rollback()
        raise RuntimeError(
            f"Failed to process file document using LlamaCloud: {e!s}"
        ) from e


async def add_received_file_document_using_docling(
    session: AsyncSession,
    file_name: str,
    docling_markdown_document: str,
    search_space_id: int,
    user_id: str,
) -> Document | None:
    """
    Process and store document content parsed by Docling.

    Args:
        session: Database session
        file_name: Name of the processed file
        docling_markdown_document: Markdown content from Docling parsing
        search_space_id: ID of the search space
        user_id: ID of the user

    Returns:
        Document object if successful, None if failed
    """
    try:
        file_in_markdown = docling_markdown_document

        # Generate unique identifier hash for this file
        unique_identifier_hash = generate_unique_identifier_hash(
            DocumentType.FILE, file_name, search_space_id
        )

        # Generate content hash
        content_hash = generate_content_hash(file_in_markdown, search_space_id)

        # Check if document with this unique identifier already exists
        existing_document = await check_document_by_unique_identifier(
            session, unique_identifier_hash
        )

        if existing_document:
            # Document exists - check if content has changed
            if existing_document.content_hash == content_hash:
                logging.info(f"Document for file {file_name} unchanged. Skipping.")
                return existing_document
            else:
                # Content has changed - update the existing document
                logging.info(
                    f"Content changed for file {file_name}. Updating document."
                )

        # Get user's long context LLM (needed for both create and update)
        user_llm = await get_user_long_context_llm(session, user_id, search_space_id)
        if not user_llm:
            raise RuntimeError(
                f"No long context LLM configured for user {user_id} in search space {search_space_id}"
            )

        # Generate summary using chunked processing for large documents
        from app.services.docling_service import create_docling_service

        docling_service = create_docling_service()

        summary_content = await docling_service.process_large_document_summary(
            content=file_in_markdown, llm=user_llm, document_title=file_name
        )

        # Enhance summary with metadata
        document_metadata = {
            "file_name": file_name,
            "etl_service": "DOCLING",
            "document_type": "File Document",
        }
        metadata_parts = []
        metadata_parts.append("# DOCUMENT METADATA")

        for key, value in document_metadata.items():
            if value:  # Only include non-empty values
                formatted_key = key.replace("_", " ").title()
                metadata_parts.append(f"**{formatted_key}:** {value}")

        metadata_section = "\n".join(metadata_parts)
        enhanced_summary_content = (
            f"{metadata_section}\n\n# DOCUMENT SUMMARY\n\n{summary_content}"
        )

        from app.config import config

        summary_embedding = config.embedding_model_instance.embed(
            enhanced_summary_content
        )

        # Process chunks
        chunks = await create_document_chunks(file_in_markdown)

        # Update or create document
        if existing_document:
            # Update existing document
            existing_document.title = file_name
            existing_document.content = enhanced_summary_content
            existing_document.content_hash = content_hash
            existing_document.embedding = summary_embedding
            existing_document.document_metadata = {
                "FILE_NAME": file_name,
                "ETL_SERVICE": "DOCLING",
            }
            existing_document.chunks = chunks

            await session.commit()
            await session.refresh(existing_document)
            document = existing_document
        else:
            # Create new document
            document = Document(
                search_space_id=search_space_id,
                title=file_name,
                document_type=DocumentType.FILE,
                document_metadata={
                    "FILE_NAME": file_name,
                    "ETL_SERVICE": "DOCLING",
                },
                content=enhanced_summary_content,
                embedding=summary_embedding,
                chunks=chunks,
                content_hash=content_hash,
                unique_identifier_hash=unique_identifier_hash,
            )

        session.add(document)
        await session.commit()
        await session.refresh(document)

        return document
    except SQLAlchemyError as db_error:
        await session.rollback()
        raise db_error
    except Exception as e:
        await session.rollback()
        raise RuntimeError(
            f"Failed to process file document using Docling: {e!s}"
        ) from e


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

            # Determine STT service type
            stt_service_type = (
                "local"
                if app_config.STT_SERVICE
                and app_config.STT_SERVICE.startswith("local/")
                else "external"
            )

            # Check if using local STT service
            if stt_service_type == "local":
                # Use local Faster-Whisper for transcription
                from app.services.stt_service import stt_service

                try:
                    result = stt_service.transcribe_file(file_path)
                    transcribed_text = result.get("text", "")

                    if not transcribed_text:
                        raise ValueError("Transcription returned empty text")

                    # Add metadata about the transcription
                    transcribed_text = (
                        f"# Transcription of {filename}\n\n{transcribed_text}"
                    )
                except Exception as e:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Failed to transcribe audio file {filename}: {e!s}",
                    ) from e

                await task_logger.log_task_progress(
                    log_entry,
                    f"Local STT transcription completed: {filename}",
                    {
                        "processing_stage": "local_transcription_complete",
                        "language": result.get("language"),
                        "confidence": result.get("language_probability"),
                        "duration": result.get("duration"),
                    },
                )
            else:
                # Use LiteLLM for audio transcription
                with open(file_path, "rb") as audio_file:
                    transcription_kwargs = {
                        "model": app_config.STT_SERVICE,
                        "file": audio_file,
                        "api_key": app_config.STT_SERVICE_API_KEY,
                    }
                    if app_config.STT_SERVICE_API_BASE:
                        transcription_kwargs["api_base"] = (
                            app_config.STT_SERVICE_API_BASE
                        )

                    transcription_response = await atranscription(
                        **transcription_kwargs
                    )

                    # Extract the transcribed text
                    transcribed_text = transcription_response.get("text", "")

                    if not transcribed_text:
                        raise ValueError("Transcription returned empty text")

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
                        "stt_service": stt_service_type,
                    },
                )
            else:
                await task_logger.log_task_success(
                    log_entry,
                    f"Audio file transcript already exists (duplicate): {filename}",
                    {"duplicate_detected": True, "file_type": "audio"},
                )

        else:
            # Import page limit service
            from app.services.page_limit_service import (
                PageLimitExceededError,
                PageLimitService,
            )

            # Initialize page limit service
            page_limit_service = PageLimitService(session)

            # CRITICAL: Estimate page count BEFORE making expensive ETL API calls
            # This prevents users from incurring costs on files that would exceed their limit
            try:
                estimated_pages_before = (
                    page_limit_service.estimate_pages_before_processing(file_path)
                )
            except Exception:
                # If estimation fails, use a conservative estimate based on file size
                import os

                file_size = os.path.getsize(file_path)
                estimated_pages_before = max(
                    1, file_size // (80 * 1024)
                )  # ~80KB per page

            await task_logger.log_task_progress(
                log_entry,
                f"Estimated {estimated_pages_before} pages for file: {filename}",
                {
                    "estimated_pages": estimated_pages_before,
                    "file_type": "document",
                },
            )

            # Check page limit BEFORE calling ETL service to avoid unnecessary costs
            try:
                await page_limit_service.check_page_limit(
                    user_id, estimated_pages_before
                )
            except PageLimitExceededError as e:
                await task_logger.log_task_failure(
                    log_entry,
                    f"Page limit exceeded before processing: {filename}",
                    str(e),
                    {
                        "error_type": "PageLimitExceeded",
                        "pages_used": e.pages_used,
                        "pages_limit": e.pages_limit,
                        "estimated_pages": estimated_pages_before,
                    },
                )
                # Clean up the temp file
                import os

                with contextlib.suppress(Exception):
                    os.unlink(file_path)

                raise HTTPException(
                    status_code=403,
                    detail=str(e),
                ) from e

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

                # Verify actual page count from parsed documents
                actual_pages = page_limit_service.estimate_pages_from_elements(docs)

                # Use the higher of the two estimates for safety (in case pre-estimate was too low)
                final_page_count = max(estimated_pages_before, actual_pages)

                # If actual is significantly higher than estimate, log a warning
                if actual_pages > estimated_pages_before * 1.5:
                    await task_logger.log_task_progress(
                        log_entry,
                        f"Actual page count higher than estimate: {filename}",
                        {
                            "estimated_before": estimated_pages_before,
                            "actual_pages": actual_pages,
                            "using_count": final_page_count,
                        },
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
                    # Update page usage after successful processing
                    # allow_exceed=True because document was already created after passing initial check
                    await page_limit_service.update_page_usage(
                        user_id, final_page_count, allow_exceed=True
                    )

                    await task_logger.log_task_success(
                        log_entry,
                        f"Successfully processed file with Unstructured: {filename}",
                        {
                            "document_id": result.id,
                            "content_hash": result.content_hash,
                            "file_type": "document",
                            "etl_service": "UNSTRUCTURED",
                            "pages_processed": final_page_count,
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

                # Check if LlamaCloud returned any documents
                if not markdown_documents or len(markdown_documents) == 0:
                    await task_logger.log_task_failure(
                        log_entry,
                        f"LlamaCloud parsing returned no documents: {filename}",
                        "ETL service returned empty document list",
                        {
                            "error_type": "EmptyDocumentList",
                            "etl_service": "LLAMACLOUD",
                        },
                    )
                    raise ValueError(
                        f"LlamaCloud parsing returned no documents for {filename}"
                    )

                # Verify actual page count from parsed markdown documents
                actual_pages = page_limit_service.estimate_pages_from_markdown(
                    markdown_documents
                )

                # Use the higher of the two estimates for safety (in case pre-estimate was too low)
                final_page_count = max(estimated_pages_before, actual_pages)

                # If actual is significantly higher than estimate, log a warning
                if actual_pages > estimated_pages_before * 1.5:
                    await task_logger.log_task_progress(
                        log_entry,
                        f"Actual page count higher than estimate: {filename}",
                        {
                            "estimated_before": estimated_pages_before,
                            "actual_pages": actual_pages,
                            "using_count": final_page_count,
                        },
                    )

                # Track if any document was successfully created (not a duplicate)
                any_doc_created = False
                last_created_doc = None

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

                    # Track if this document was successfully created
                    if doc_result:
                        any_doc_created = True
                        last_created_doc = doc_result

                # Update page usage once after processing all documents
                # Only update if at least one document was created (not all duplicates)
                if any_doc_created:
                    # Update page usage after successful processing
                    # allow_exceed=True because document was already created after passing initial check
                    await page_limit_service.update_page_usage(
                        user_id, final_page_count, allow_exceed=True
                    )

                    await task_logger.log_task_success(
                        log_entry,
                        f"Successfully processed file with LlamaCloud: {filename}",
                        {
                            "document_id": last_created_doc.id,
                            "content_hash": last_created_doc.content_hash,
                            "file_type": "document",
                            "etl_service": "LLAMACLOUD",
                            "pages_processed": final_page_count,
                            "documents_count": len(markdown_documents),
                        },
                    )
                else:
                    # All documents were duplicates (markdown_documents was not empty, but all returned None)
                    await task_logger.log_task_success(
                        log_entry,
                        f"Document already exists (duplicate): {filename}",
                        {
                            "duplicate_detected": True,
                            "file_type": "document",
                            "etl_service": "LLAMACLOUD",
                            "documents_count": len(markdown_documents),
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

                # Suppress pdfminer warnings that can cause processing to hang
                # These warnings are harmless but can spam logs and potentially halt processing
                # Suppress both Python warnings and logging warnings from pdfminer
                pdfminer_logger = getLogger("pdfminer")
                original_level = pdfminer_logger.level

                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        "ignore", category=UserWarning, module="pdfminer"
                    )
                    warnings.filterwarnings(
                        "ignore",
                        message=".*Cannot set gray non-stroke color.*",
                    )
                    warnings.filterwarnings("ignore", message=".*invalid float value.*")

                    # Temporarily suppress pdfminer logging warnings
                    pdfminer_logger.setLevel(ERROR)

                    try:
                        # Process the document
                        result = await docling_service.process_document(
                            file_path, filename
                        )
                    finally:
                        # Restore original logging level
                        pdfminer_logger.setLevel(original_level)

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

                # Verify actual page count from content length
                actual_pages = page_limit_service.estimate_pages_from_content_length(
                    len(result["content"])
                )

                # Use the higher of the two estimates for safety (in case pre-estimate was too low)
                final_page_count = max(estimated_pages_before, actual_pages)

                # If actual is significantly higher than estimate, log a warning
                if actual_pages > estimated_pages_before * 1.5:
                    await task_logger.log_task_progress(
                        log_entry,
                        f"Actual page count higher than estimate: {filename}",
                        {
                            "estimated_before": estimated_pages_before,
                            "actual_pages": actual_pages,
                            "using_count": final_page_count,
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
                    # Update page usage after successful processing
                    # allow_exceed=True because document was already created after passing initial check
                    await page_limit_service.update_page_usage(
                        user_id, final_page_count, allow_exceed=True
                    )

                    await task_logger.log_task_success(
                        log_entry,
                        f"Successfully processed file with Docling: {filename}",
                        {
                            "document_id": doc_result.id,
                            "content_hash": doc_result.content_hash,
                            "file_type": "document",
                            "etl_service": "DOCLING",
                            "pages_processed": final_page_count,
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

        # For page limit errors, use the detailed message from the exception
        from app.services.page_limit_service import PageLimitExceededError

        if isinstance(e, PageLimitExceededError):
            error_message = str(e)
        elif isinstance(e, HTTPException) and "page limit" in str(e.detail).lower():
            error_message = str(e.detail)
        else:
            error_message = f"Failed to process file: {filename}"

        await task_logger.log_task_failure(
            log_entry,
            error_message,
            str(e),
            {"error_type": type(e).__name__, "filename": filename},
        )
        import logging

        logging.error(f"Error processing file in background: {error_message}")
        raise  # Re-raise so the wrapper can also handle it
