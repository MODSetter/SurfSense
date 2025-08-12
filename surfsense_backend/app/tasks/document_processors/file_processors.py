"""
File document processors for different ETL services (Unstructured, LlamaCloud, Docling).
"""

import logging

from langchain_core.documents import Document as LangChainDocument
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, DocumentType
from app.services.llm_service import get_user_long_context_llm
from app.utils.document_converters import (
    convert_document_to_markdown,
    generate_content_hash,
)

from .base import (
    check_duplicate_document,
    create_document_chunks,
    generate_document_summary,
)


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

        content_hash = generate_content_hash(file_in_markdown, search_space_id)

        # Check if document with this content hash already exists
        existing_document = await check_duplicate_document(session, content_hash)
        if existing_document:
            logging.info(
                f"Document with content hash {content_hash} already exists. Skipping processing."
            )
            return existing_document

        # TODO: Check if file_markdown exceeds token limit of embedding model

        # Get user's long context LLM
        user_llm = await get_user_long_context_llm(session, user_id)
        if not user_llm:
            raise RuntimeError(f"No long context LLM configured for user {user_id}")

        # Generate summary
        summary_content, summary_embedding = await generate_document_summary(
            file_in_markdown, user_llm
        )

        # Process chunks
        chunks = await create_document_chunks(file_in_markdown)

        # Create and store document
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

        content_hash = generate_content_hash(file_in_markdown, search_space_id)

        # Check if document with this content hash already exists
        existing_document = await check_duplicate_document(session, content_hash)
        if existing_document:
            logging.info(
                f"Document with content hash {content_hash} already exists. Skipping processing."
            )
            return existing_document

        # Get user's long context LLM
        user_llm = await get_user_long_context_llm(session, user_id)
        if not user_llm:
            raise RuntimeError(f"No long context LLM configured for user {user_id}")

        # Generate summary
        summary_content, summary_embedding = await generate_document_summary(
            file_in_markdown, user_llm
        )

        # Process chunks
        chunks = await create_document_chunks(file_in_markdown)

        # Create and store document
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

        content_hash = generate_content_hash(file_in_markdown, search_space_id)

        # Check if document with this content hash already exists
        existing_document = await check_duplicate_document(session, content_hash)
        if existing_document:
            logging.info(
                f"Document with content hash {content_hash} already exists. Skipping processing."
            )
            return existing_document

        # Get user's long context LLM
        user_llm = await get_user_long_context_llm(session, user_id)
        if not user_llm:
            raise RuntimeError(f"No long context LLM configured for user {user_id}")

        # Generate summary using chunked processing for large documents
        from app.services.docling_service import create_docling_service

        docling_service = create_docling_service()

        summary_content = await docling_service.process_large_document_summary(
            content=file_in_markdown, llm=user_llm, document_title=file_name
        )

        from app.config import config

        summary_embedding = config.embedding_model_instance.embed(summary_content)

        # Process chunks
        chunks = await create_document_chunks(file_in_markdown)

        # Create and store document
        document = Document(
            search_space_id=search_space_id,
            title=file_name,
            document_type=DocumentType.FILE,
            document_metadata={
                "FILE_NAME": file_name,
                "ETL_SERVICE": "DOCLING",
            },
            content=summary_content,
            embedding=summary_embedding,
            chunks=chunks,
            content_hash=content_hash,
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
