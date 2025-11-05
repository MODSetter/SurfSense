"""
URL crawler document processor.
"""

import logging

import validators
from firecrawl import AsyncFirecrawlApp
from langchain_community.document_loaders import AsyncChromiumLoader
from langchain_core.documents import Document as LangchainDocument
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import Document, DocumentType
from app.services.llm_service import get_user_long_context_llm
from app.services.task_logging_service import TaskLoggingService
from app.utils.document_converters import (
    create_document_chunks,
    generate_content_hash,
    generate_document_summary,
    generate_unique_identifier_hash,
)

from .base import (
    check_document_by_unique_identifier,
    md,
)


async def add_crawled_url_document(
    session: AsyncSession, url: str, search_space_id: int, user_id: str
) -> Document | None:
    """
    Process and store a document from a crawled URL.

    Args:
        session: Database session
        url: URL to crawl
        search_space_id: ID of the search space
        user_id: ID of the user

    Returns:
        Document object if successful, None if failed
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="crawl_url_document",
        source="background_task",
        message=f"Starting URL crawling process for: {url}",
        metadata={"url": url, "user_id": str(user_id)},
    )

    try:
        # URL validation step
        await task_logger.log_task_progress(
            log_entry, f"Validating URL: {url}", {"stage": "validation"}
        )

        if not validators.url(url):
            raise ValueError(f"Url {url} is not a valid URL address")

        # Set up crawler
        await task_logger.log_task_progress(
            log_entry,
            f"Setting up crawler for URL: {url}",
            {
                "stage": "crawler_setup",
                "firecrawl_available": bool(config.FIRECRAWL_API_KEY),
            },
        )

        use_firecrawl = bool(config.FIRECRAWL_API_KEY)

        if use_firecrawl:
            # Use Firecrawl SDK directly
            firecrawl_app = AsyncFirecrawlApp(api_key=config.FIRECRAWL_API_KEY)
        else:
            crawl_loader = AsyncChromiumLoader(urls=[url], headless=True)

        # Perform crawling
        await task_logger.log_task_progress(
            log_entry,
            f"Crawling URL content: {url}",
            {
                "stage": "crawling",
                "crawler_type": "AsyncFirecrawlApp"
                if use_firecrawl
                else "AsyncChromiumLoader",
            },
        )

        if use_firecrawl:
            # Use async Firecrawl SDK with v1 API - properly awaited
            scrape_result = await firecrawl_app.scrape_url(
                url=url, formats=["markdown"]
            )

            # scrape_result is a Pydantic ScrapeResponse object
            # Access attributes directly
            if scrape_result and scrape_result.success:
                # Extract markdown content
                markdown_content = scrape_result.markdown or ""

                # Extract metadata - this is a DICT
                metadata = scrape_result.metadata if scrape_result.metadata else {}

                # Convert to LangChain Document format
                url_crawled = [
                    LangchainDocument(
                        page_content=markdown_content,
                        metadata={
                            "source": url,
                            "title": metadata.get("title", url),
                            "description": metadata.get("description", ""),
                            "language": metadata.get("language", ""),
                            "sourceURL": metadata.get("sourceURL", url),
                            **metadata,  # Include all other metadata fields
                        },
                    )
                ]
                content_in_markdown = url_crawled[0].page_content
            else:
                error_msg = (
                    scrape_result.error
                    if scrape_result and hasattr(scrape_result, "error")
                    else "Unknown error"
                )
                raise ValueError(f"Firecrawl failed to scrape URL: {error_msg}")
        else:
            # Use AsyncChromiumLoader as fallback
            url_crawled = await crawl_loader.aload()
            content_in_markdown = md.transform_documents(url_crawled)[0].page_content

        # Format document
        await task_logger.log_task_progress(
            log_entry,
            f"Processing crawled content from: {url}",
            {"stage": "content_processing", "content_length": len(content_in_markdown)},
        )

        # Format document metadata in a more maintainable way
        metadata_sections = [
            (
                "METADATA",
                [
                    f"{key.upper()}: {value}"
                    for key, value in url_crawled[0].metadata.items()
                ],
            ),
            (
                "CONTENT",
                ["FORMAT: markdown", "TEXT_START", content_in_markdown, "TEXT_END"],
            ),
        ]

        # Build the document string more efficiently
        document_parts = []
        document_parts.append("<DOCUMENT>")

        for section_title, section_content in metadata_sections:
            document_parts.append(f"<{section_title}>")
            document_parts.extend(section_content)
            document_parts.append(f"</{section_title}>")

        document_parts.append("</DOCUMENT>")
        combined_document_string = "\n".join(document_parts)

        # Generate unique identifier hash for this URL
        unique_identifier_hash = generate_unique_identifier_hash(
            DocumentType.CRAWLED_URL, url, search_space_id
        )

        # Generate content hash
        content_hash = generate_content_hash(combined_document_string, search_space_id)

        # Check if document with this unique identifier already exists
        await task_logger.log_task_progress(
            log_entry,
            f"Checking for existing URL: {url}",
            {"stage": "duplicate_check", "url": url},
        )

        existing_document = await check_document_by_unique_identifier(
            session, unique_identifier_hash
        )

        if existing_document:
            # Document exists - check if content has changed
            if existing_document.content_hash == content_hash:
                await task_logger.log_task_success(
                    log_entry,
                    f"URL document unchanged: {url}",
                    {
                        "duplicate_detected": True,
                        "existing_document_id": existing_document.id,
                    },
                )
                logging.info(f"Document for URL {url} unchanged. Skipping.")
                return existing_document
            else:
                # Content has changed - update the existing document
                logging.info(f"Content changed for URL {url}. Updating document.")
                await task_logger.log_task_progress(
                    log_entry,
                    f"Updating URL document: {url}",
                    {"stage": "document_update", "url": url},
                )

        # Get LLM for summary generation (needed for both create and update)
        await task_logger.log_task_progress(
            log_entry,
            f"Preparing for summary generation: {url}",
            {"stage": "llm_setup"},
        )

        # Get user's long context LLM
        user_llm = await get_user_long_context_llm(session, user_id, search_space_id)
        if not user_llm:
            raise RuntimeError(
                f"No long context LLM configured for user {user_id} in search space {search_space_id}"
            )

        # Generate summary
        await task_logger.log_task_progress(
            log_entry,
            f"Generating summary for URL content: {url}",
            {"stage": "summary_generation"},
        )

        # Generate summary with metadata
        document_metadata = {
            "url": url,
            "title": url_crawled[0].metadata.get("title", url),
            "document_type": "Crawled URL Document",
            "crawler_type": "FirecrawlApp" if use_firecrawl else "AsyncChromiumLoader",
        }
        summary_content, summary_embedding = await generate_document_summary(
            combined_document_string, user_llm, document_metadata
        )

        # Process chunks
        await task_logger.log_task_progress(
            log_entry,
            f"Processing content chunks for URL: {url}",
            {"stage": "chunk_processing"},
        )

        chunks = await create_document_chunks(content_in_markdown)

        # Update or create document
        if existing_document:
            # Update existing document
            await task_logger.log_task_progress(
                log_entry,
                f"Updating document in database for URL: {url}",
                {"stage": "document_update", "chunks_count": len(chunks)},
            )

            existing_document.title = url_crawled[0].metadata.get(
                "title", url_crawled[0].metadata.get("source", url)
            )
            existing_document.content = summary_content
            existing_document.content_hash = content_hash
            existing_document.embedding = summary_embedding
            existing_document.document_metadata = url_crawled[0].metadata
            existing_document.chunks = chunks

            document = existing_document
        else:
            # Create new document
            await task_logger.log_task_progress(
                log_entry,
                f"Creating document in database for URL: {url}",
                {"stage": "document_creation", "chunks_count": len(chunks)},
            )

            document = Document(
                search_space_id=search_space_id,
                title=url_crawled[0].metadata.get(
                    "title", url_crawled[0].metadata.get("source", url)
                ),
                document_type=DocumentType.CRAWLED_URL,
                document_metadata=url_crawled[0].metadata,
                content=summary_content,
                embedding=summary_embedding,
                chunks=chunks,
                content_hash=content_hash,
                unique_identifier_hash=unique_identifier_hash,
            )

            session.add(document)
        await session.commit()
        await session.refresh(document)

        # Log success
        await task_logger.log_task_success(
            log_entry,
            f"Successfully crawled and processed URL: {url}",
            {
                "document_id": document.id,
                "title": document.title,
                "content_hash": content_hash,
                "chunks_count": len(chunks),
                "summary_length": len(summary_content),
            },
        )

        return document

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error while processing URL: {url}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        raise db_error
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to crawl URL: {url}",
            str(e),
            {"error_type": type(e).__name__},
        )
        raise RuntimeError(f"Failed to crawl URL: {e!s}") from e
