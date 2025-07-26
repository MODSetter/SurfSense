import logging
from urllib.parse import parse_qs, urlparse

import aiohttp
import validators
from langchain_community.document_loaders import AsyncChromiumLoader, FireCrawlLoader
from langchain_community.document_transformers import MarkdownifyTransformer
from langchain_core.documents import Document as LangChainDocument
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from youtube_transcript_api import YouTubeTranscriptApi

from app.config import config
from app.db import Chunk, Document, DocumentType
from app.prompts import SUMMARY_PROMPT_TEMPLATE
from app.schemas import ExtensionDocumentContent
from app.services.llm_service import get_user_long_context_llm
from app.services.task_logging_service import TaskLoggingService
from app.utils.document_converters import (
    convert_document_to_markdown,
    generate_content_hash,
)

md = MarkdownifyTransformer()


async def add_crawled_url_document(
    session: AsyncSession, url: str, search_space_id: int, user_id: str
) -> Document | None:
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

        if config.FIRECRAWL_API_KEY:
            crawl_loader = FireCrawlLoader(
                url=url,
                api_key=config.FIRECRAWL_API_KEY,
                mode="scrape",
                params={
                    "formats": ["markdown"],
                    "excludeTags": ["a"],
                },
            )
        else:
            crawl_loader = AsyncChromiumLoader(urls=[url], headless=True)

        # Perform crawling
        await task_logger.log_task_progress(
            log_entry,
            f"Crawling URL content: {url}",
            {"stage": "crawling", "crawler_type": type(crawl_loader).__name__},
        )

        url_crawled = await crawl_loader.aload()

        if isinstance(crawl_loader, FireCrawlLoader):
            content_in_markdown = url_crawled[0].page_content
        elif isinstance(crawl_loader, AsyncChromiumLoader):
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
        content_hash = generate_content_hash(combined_document_string, search_space_id)

        # Check for duplicates
        await task_logger.log_task_progress(
            log_entry,
            f"Checking for duplicate content: {url}",
            {"stage": "duplicate_check", "content_hash": content_hash},
        )

        # Check if document with this content hash already exists
        existing_doc_result = await session.execute(
            select(Document).where(Document.content_hash == content_hash)
        )
        existing_document = existing_doc_result.scalars().first()

        if existing_document:
            await task_logger.log_task_success(
                log_entry,
                f"Document already exists for URL: {url}",
                {
                    "duplicate_detected": True,
                    "existing_document_id": existing_document.id,
                },
            )
            logging.info(
                f"Document with content hash {content_hash} already exists. Skipping processing."
            )
            return existing_document

        # Get LLM for summary generation
        await task_logger.log_task_progress(
            log_entry,
            f"Preparing for summary generation: {url}",
            {"stage": "llm_setup"},
        )

        # Get user's long context LLM
        user_llm = await get_user_long_context_llm(session, user_id)
        if not user_llm:
            raise RuntimeError(f"No long context LLM configured for user {user_id}")

        # Generate summary
        await task_logger.log_task_progress(
            log_entry,
            f"Generating summary for URL content: {url}",
            {"stage": "summary_generation"},
        )

        summary_chain = SUMMARY_PROMPT_TEMPLATE | user_llm
        summary_result = await summary_chain.ainvoke(
            {"document": combined_document_string}
        )
        summary_content = summary_result.content
        summary_embedding = config.embedding_model_instance.embed(summary_content)

        # Process chunks
        await task_logger.log_task_progress(
            log_entry,
            f"Processing content chunks for URL: {url}",
            {"stage": "chunk_processing"},
        )

        chunks = [
            Chunk(
                content=chunk.text,
                embedding=config.embedding_model_instance.embed(chunk.text),
            )
            for chunk in config.chunker_instance.chunk(content_in_markdown)
        ]

        # Create and store document
        await task_logger.log_task_progress(
            log_entry,
            f"Creating document in database for URL: {url}",
            {"stage": "document_creation", "chunks_count": len(chunks)},
        )

        document = Document(
            search_space_id=search_space_id,
            title=url_crawled[0].metadata["title"]
            if isinstance(crawl_loader, FireCrawlLoader)
            else url_crawled[0].metadata["source"],
            document_type=DocumentType.CRAWLED_URL,
            document_metadata=url_crawled[0].metadata,
            content=summary_content,
            embedding=summary_embedding,
            chunks=chunks,
            content_hash=content_hash,
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


async def add_extension_received_document(
    session: AsyncSession,
    content: ExtensionDocumentContent,
    search_space_id: int,
    user_id: str,
) -> Document | None:
    """
    Process and store document content received from the SurfSense Extension.

    Args:
        session: Database session
        content: Document content from extension
        search_space_id: ID of the search space

    Returns:
        Document object if successful, None if failed
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="extension_document",
        source="background_task",
        message=f"Processing extension document: {content.metadata.VisitedWebPageTitle}",
        metadata={
            "url": content.metadata.VisitedWebPageURL,
            "title": content.metadata.VisitedWebPageTitle,
            "user_id": str(user_id),
        },
    )

    try:
        # Format document metadata in a more maintainable way
        metadata_sections = [
            (
                "METADATA",
                [
                    f"SESSION_ID: {content.metadata.BrowsingSessionId}",
                    f"URL: {content.metadata.VisitedWebPageURL}",
                    f"TITLE: {content.metadata.VisitedWebPageTitle}",
                    f"REFERRER: {content.metadata.VisitedWebPageReffererURL}",
                    f"TIMESTAMP: {content.metadata.VisitedWebPageDateWithTimeInISOString}",
                    f"DURATION_MS: {content.metadata.VisitedWebPageVisitDurationInMilliseconds}",
                ],
            ),
            (
                "CONTENT",
                ["FORMAT: markdown", "TEXT_START", content.pageContent, "TEXT_END"],
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
        content_hash = generate_content_hash(combined_document_string, search_space_id)

        # Check if document with this content hash already exists
        existing_doc_result = await session.execute(
            select(Document).where(Document.content_hash == content_hash)
        )
        existing_document = existing_doc_result.scalars().first()

        if existing_document:
            await task_logger.log_task_success(
                log_entry,
                f"Extension document already exists: {content.metadata.VisitedWebPageTitle}",
                {
                    "duplicate_detected": True,
                    "existing_document_id": existing_document.id,
                },
            )
            logging.info(
                f"Document with content hash {content_hash} already exists. Skipping processing."
            )
            return existing_document

        # Get user's long context LLM
        user_llm = await get_user_long_context_llm(session, user_id)
        if not user_llm:
            raise RuntimeError(f"No long context LLM configured for user {user_id}")

        # Generate summary
        summary_chain = SUMMARY_PROMPT_TEMPLATE | user_llm
        summary_result = await summary_chain.ainvoke(
            {"document": combined_document_string}
        )
        summary_content = summary_result.content
        summary_embedding = config.embedding_model_instance.embed(summary_content)

        # Process chunks
        chunks = [
            Chunk(
                content=chunk.text,
                embedding=config.embedding_model_instance.embed(chunk.text),
            )
            for chunk in config.chunker_instance.chunk(content.pageContent)
        ]

        # Create and store document
        document = Document(
            search_space_id=search_space_id,
            title=content.metadata.VisitedWebPageTitle,
            document_type=DocumentType.EXTENSION,
            document_metadata=content.metadata.model_dump(),
            content=summary_content,
            embedding=summary_embedding,
            chunks=chunks,
            content_hash=content_hash,
        )

        session.add(document)
        await session.commit()
        await session.refresh(document)

        # Log success
        await task_logger.log_task_success(
            log_entry,
            f"Successfully processed extension document: {content.metadata.VisitedWebPageTitle}",
            {
                "document_id": document.id,
                "content_hash": content_hash,
                "url": content.metadata.VisitedWebPageURL,
            },
        )

        return document

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error processing extension document: {content.metadata.VisitedWebPageTitle}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        raise db_error
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to process extension document: {content.metadata.VisitedWebPageTitle}",
            str(e),
            {"error_type": type(e).__name__},
        )
        raise RuntimeError(f"Failed to process extension document: {e!s}") from e


async def add_received_markdown_file_document(
    session: AsyncSession,
    file_name: str,
    file_in_markdown: str,
    search_space_id: int,
    user_id: str,
) -> Document | None:
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="markdown_file_document",
        source="background_task",
        message=f"Processing markdown file: {file_name}",
        metadata={
            "filename": file_name,
            "user_id": str(user_id),
            "content_length": len(file_in_markdown),
        },
    )

    try:
        content_hash = generate_content_hash(file_in_markdown, search_space_id)

        # Check if document with this content hash already exists
        existing_doc_result = await session.execute(
            select(Document).where(Document.content_hash == content_hash)
        )
        existing_document = existing_doc_result.scalars().first()

        if existing_document:
            await task_logger.log_task_success(
                log_entry,
                f"Markdown file document already exists: {file_name}",
                {
                    "duplicate_detected": True,
                    "existing_document_id": existing_document.id,
                },
            )
            logging.info(
                f"Document with content hash {content_hash} already exists. Skipping processing."
            )
            return existing_document

        # Get user's long context LLM
        user_llm = await get_user_long_context_llm(session, user_id)
        if not user_llm:
            raise RuntimeError(f"No long context LLM configured for user {user_id}")

        # Generate summary
        summary_chain = SUMMARY_PROMPT_TEMPLATE | user_llm
        summary_result = await summary_chain.ainvoke({"document": file_in_markdown})
        summary_content = summary_result.content
        summary_embedding = config.embedding_model_instance.embed(summary_content)

        # Process chunks
        chunks = [
            Chunk(
                content=chunk.text,
                embedding=config.embedding_model_instance.embed(chunk.text),
            )
            for chunk in config.chunker_instance.chunk(file_in_markdown)
        ]

        # Create and store document
        document = Document(
            search_space_id=search_space_id,
            title=file_name,
            document_type=DocumentType.FILE,
            document_metadata={
                "FILE_NAME": file_name,
            },
            content=summary_content,
            embedding=summary_embedding,
            chunks=chunks,
            content_hash=content_hash,
        )

        session.add(document)
        await session.commit()
        await session.refresh(document)

        # Log success
        await task_logger.log_task_success(
            log_entry,
            f"Successfully processed markdown file: {file_name}",
            {
                "document_id": document.id,
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
            f"Database error processing markdown file: {file_name}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        raise db_error
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to process markdown file: {file_name}",
            str(e),
            {"error_type": type(e).__name__},
        )
        raise RuntimeError(f"Failed to process file document: {e!s}") from e


async def add_received_file_document_using_unstructured(
    session: AsyncSession,
    file_name: str,
    unstructured_processed_elements: list[LangChainDocument],
    search_space_id: int,
    user_id: str,
) -> Document | None:
    try:
        file_in_markdown = await convert_document_to_markdown(
            unstructured_processed_elements
        )

        content_hash = generate_content_hash(file_in_markdown, search_space_id)

        # Check if document with this content hash already exists
        existing_doc_result = await session.execute(
            select(Document).where(Document.content_hash == content_hash)
        )
        existing_document = existing_doc_result.scalars().first()

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
        summary_chain = SUMMARY_PROMPT_TEMPLATE | user_llm
        summary_result = await summary_chain.ainvoke({"document": file_in_markdown})
        summary_content = summary_result.content
        summary_embedding = config.embedding_model_instance.embed(summary_content)

        # Process chunks
        chunks = [
            Chunk(
                content=chunk.text,
                embedding=config.embedding_model_instance.embed(chunk.text),
            )
            for chunk in config.chunker_instance.chunk(file_in_markdown)
        ]

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
        llamacloud_markdown_documents: List of markdown content from LlamaCloud parsing
        search_space_id: ID of the search space

    Returns:
        Document object if successful, None if failed
    """
    try:
        # Combine all markdown documents into one
        file_in_markdown = llamacloud_markdown_document

        content_hash = generate_content_hash(file_in_markdown, search_space_id)

        # Check if document with this content hash already exists
        existing_doc_result = await session.execute(
            select(Document).where(Document.content_hash == content_hash)
        )
        existing_document = existing_doc_result.scalars().first()

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
        summary_chain = SUMMARY_PROMPT_TEMPLATE | user_llm
        summary_result = await summary_chain.ainvoke({"document": file_in_markdown})
        summary_content = summary_result.content
        summary_embedding = config.embedding_model_instance.embed(summary_content)

        # Process chunks
        chunks = [
            Chunk(
                content=chunk.text,
                embedding=config.embedding_model_instance.embed(chunk.text),
            )
            for chunk in config.chunker_instance.chunk(file_in_markdown)
        ]

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
        existing_doc_result = await session.execute(
            select(Document).where(Document.content_hash == content_hash)
        )
        existing_document = existing_doc_result.scalars().first()

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
        summary_embedding = config.embedding_model_instance.embed(summary_content)

        # Process chunks
        chunks = [
            Chunk(
                content=chunk.text,
                embedding=config.embedding_model_instance.embed(chunk.text),
            )
            for chunk in config.chunker_instance.chunk(file_in_markdown)
        ]

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


async def add_youtube_video_document(
    session: AsyncSession, url: str, search_space_id: int, user_id: str
):
    """
    Process a YouTube video URL, extract transcripts, and store as a document.

    Args:
        session: Database session for storing the document
        url: YouTube video URL (supports standard, shortened, and embed formats)
        search_space_id: ID of the search space to add the document to

    Returns:
        Document: The created document object

    Raises:
        ValueError: If the YouTube video ID cannot be extracted from the URL
        SQLAlchemyError: If there's a database error
        RuntimeError: If the video processing fails
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="youtube_video_document",
        source="background_task",
        message=f"Starting YouTube video processing for: {url}",
        metadata={"url": url, "user_id": str(user_id)},
    )

    try:
        # Extract video ID from URL
        await task_logger.log_task_progress(
            log_entry,
            f"Extracting video ID from URL: {url}",
            {"stage": "video_id_extraction"},
        )

        def get_youtube_video_id(url: str):
            parsed_url = urlparse(url)
            hostname = parsed_url.hostname

            if hostname == "youtu.be":
                return parsed_url.path[1:]
            if hostname in ("www.youtube.com", "youtube.com"):
                if parsed_url.path == "/watch":
                    query_params = parse_qs(parsed_url.query)
                    return query_params.get("v", [None])[0]
                if parsed_url.path.startswith("/embed/"):
                    return parsed_url.path.split("/")[2]
                if parsed_url.path.startswith("/v/"):
                    return parsed_url.path.split("/")[2]
            return None

        # Get video ID
        video_id = get_youtube_video_id(url)
        if not video_id:
            raise ValueError(f"Could not extract video ID from URL: {url}")

        await task_logger.log_task_progress(
            log_entry,
            f"Video ID extracted: {video_id}",
            {"stage": "video_id_extracted", "video_id": video_id},
        )

        # Get video metadata
        await task_logger.log_task_progress(
            log_entry,
            f"Fetching video metadata for: {video_id}",
            {"stage": "metadata_fetch"},
        )

        params = {
            "format": "json",
            "url": f"https://www.youtube.com/watch?v={video_id}",
        }
        oembed_url = "https://www.youtube.com/oembed"

        async with (
            aiohttp.ClientSession() as http_session,
            http_session.get(oembed_url, params=params) as response,
        ):
            video_data = await response.json()

        await task_logger.log_task_progress(
            log_entry,
            f"Video metadata fetched: {video_data.get('title', 'Unknown')}",
            {
                "stage": "metadata_fetched",
                "title": video_data.get("title"),
                "author": video_data.get("author_name"),
            },
        )

        # Get video transcript
        await task_logger.log_task_progress(
            log_entry,
            f"Fetching transcript for video: {video_id}",
            {"stage": "transcript_fetch"},
        )

        try:
            captions = YouTubeTranscriptApi.get_transcript(video_id)
            # Include complete caption information with timestamps
            transcript_segments = []
            for line in captions:
                start_time = line.get("start", 0)
                duration = line.get("duration", 0)
                text = line.get("text", "")
                timestamp = f"[{start_time:.2f}s-{start_time + duration:.2f}s]"
                transcript_segments.append(f"{timestamp} {text}")
            transcript_text = "\n".join(transcript_segments)

            await task_logger.log_task_progress(
                log_entry,
                f"Transcript fetched successfully: {len(captions)} segments",
                {
                    "stage": "transcript_fetched",
                    "segments_count": len(captions),
                    "transcript_length": len(transcript_text),
                },
            )
        except Exception as e:
            transcript_text = f"No captions available for this video. Error: {e!s}"
            await task_logger.log_task_progress(
                log_entry,
                f"No transcript available for video: {video_id}",
                {"stage": "transcript_unavailable", "error": str(e)},
            )

        # Format document
        await task_logger.log_task_progress(
            log_entry,
            f"Processing video content: {video_data.get('title', 'YouTube Video')}",
            {"stage": "content_processing"},
        )

        # Format document metadata in a more maintainable way
        metadata_sections = [
            (
                "METADATA",
                [
                    f"TITLE: {video_data.get('title', 'YouTube Video')}",
                    f"URL: {url}",
                    f"VIDEO_ID: {video_id}",
                    f"AUTHOR: {video_data.get('author_name', 'Unknown')}",
                    f"THUMBNAIL: {video_data.get('thumbnail_url', '')}",
                ],
            ),
            (
                "CONTENT",
                ["FORMAT: transcript", "TEXT_START", transcript_text, "TEXT_END"],
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
        content_hash = generate_content_hash(combined_document_string, search_space_id)

        # Check for duplicates
        await task_logger.log_task_progress(
            log_entry,
            f"Checking for duplicate video content: {video_id}",
            {"stage": "duplicate_check", "content_hash": content_hash},
        )

        # Check if document with this content hash already exists
        existing_doc_result = await session.execute(
            select(Document).where(Document.content_hash == content_hash)
        )
        existing_document = existing_doc_result.scalars().first()

        if existing_document:
            await task_logger.log_task_success(
                log_entry,
                f"YouTube video document already exists: {video_data.get('title', 'YouTube Video')}",
                {
                    "duplicate_detected": True,
                    "existing_document_id": existing_document.id,
                    "video_id": video_id,
                },
            )
            logging.info(
                f"Document with content hash {content_hash} already exists. Skipping processing."
            )
            return existing_document

        # Get LLM for summary generation
        await task_logger.log_task_progress(
            log_entry,
            f"Preparing for summary generation: {video_data.get('title', 'YouTube Video')}",
            {"stage": "llm_setup"},
        )

        # Get user's long context LLM
        user_llm = await get_user_long_context_llm(session, user_id)
        if not user_llm:
            raise RuntimeError(f"No long context LLM configured for user {user_id}")

        # Generate summary
        await task_logger.log_task_progress(
            log_entry,
            f"Generating summary for video: {video_data.get('title', 'YouTube Video')}",
            {"stage": "summary_generation"},
        )

        summary_chain = SUMMARY_PROMPT_TEMPLATE | user_llm
        summary_result = await summary_chain.ainvoke(
            {"document": combined_document_string}
        )
        summary_content = summary_result.content
        summary_embedding = config.embedding_model_instance.embed(summary_content)

        # Process chunks
        await task_logger.log_task_progress(
            log_entry,
            f"Processing content chunks for video: {video_data.get('title', 'YouTube Video')}",
            {"stage": "chunk_processing"},
        )

        chunks = [
            Chunk(
                content=chunk.text,
                embedding=config.embedding_model_instance.embed(chunk.text),
            )
            for chunk in config.chunker_instance.chunk(combined_document_string)
        ]

        # Create document
        await task_logger.log_task_progress(
            log_entry,
            f"Creating YouTube video document in database: {video_data.get('title', 'YouTube Video')}",
            {"stage": "document_creation", "chunks_count": len(chunks)},
        )

        document = Document(
            title=video_data.get("title", "YouTube Video"),
            document_type=DocumentType.YOUTUBE_VIDEO,
            document_metadata={
                "url": url,
                "video_id": video_id,
                "video_title": video_data.get("title", "YouTube Video"),
                "author": video_data.get("author_name", "Unknown"),
                "thumbnail": video_data.get("thumbnail_url", ""),
            },
            content=summary_content,
            embedding=summary_embedding,
            chunks=chunks,
            search_space_id=search_space_id,
            content_hash=content_hash,
        )

        session.add(document)
        await session.commit()
        await session.refresh(document)

        # Log success
        await task_logger.log_task_success(
            log_entry,
            f"Successfully processed YouTube video: {video_data.get('title', 'YouTube Video')}",
            {
                "document_id": document.id,
                "video_id": video_id,
                "title": document.title,
                "content_hash": content_hash,
                "chunks_count": len(chunks),
                "summary_length": len(summary_content),
                "has_transcript": "No captions available" not in transcript_text,
            },
        )

        return document
    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error while processing YouTube video: {url}",
            str(db_error),
            {
                "error_type": "SQLAlchemyError",
                "video_id": video_id if "video_id" in locals() else None,
            },
        )
        raise db_error
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to process YouTube video: {url}",
            str(e),
            {
                "error_type": type(e).__name__,
                "video_id": video_id if "video_id" in locals() else None,
            },
        )
        logging.error(f"Failed to process YouTube video: {e!s}")
        raise
