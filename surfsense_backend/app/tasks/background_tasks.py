from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from app.db import Document, DocumentType, Chunk
from app.schemas import ExtensionDocumentContent
from app.config import config
from app.prompts import SUMMARY_PROMPT_TEMPLATE
from datetime import datetime
from app.utils.document_converters import convert_document_to_markdown
from langchain_core.documents import Document as LangChainDocument
from langchain_community.document_loaders import FireCrawlLoader, AsyncChromiumLoader
from langchain_community.document_transformers import MarkdownifyTransformer
import validators
from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs
import aiohttp
from app.db import Document as DB_Document, DocumentType as DB_DocumentType
import logging

md = MarkdownifyTransformer()


async def add_crawled_url_document(
    session: AsyncSession, url: str, search_space_id: int
) -> Optional[Document]:
    try:
        if not validators.url(url):
            raise ValueError(f"Url {url} is not a valid URL address")

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

        url_crawled = await crawl_loader.aload()

        if type(crawl_loader) == FireCrawlLoader:
            content_in_markdown = url_crawled[0].page_content
        elif type(crawl_loader) == AsyncChromiumLoader:
            content_in_markdown = md.transform_documents(url_crawled)[0].page_content

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

        # Generate summary
        summary_chain = SUMMARY_PROMPT_TEMPLATE | config.long_context_llm_instance
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
            for chunk in config.chunker_instance.chunk(content_in_markdown)
        ]

        # Create and store document
        document = Document(
            search_space_id=search_space_id,
            title=url_crawled[0].metadata["title"]
            if type(crawl_loader) == FireCrawlLoader
            else url_crawled[0].metadata["source"],
            document_type=DocumentType.CRAWLED_URL,
            document_metadata=url_crawled[0].metadata,
            content=summary_content,
            embedding=summary_embedding,
            chunks=chunks,
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
        raise RuntimeError(f"Failed to crawl URL: {str(e)}")


async def add_extension_received_document(
    session: AsyncSession, content: ExtensionDocumentContent, search_space_id: int
) -> Optional[Document]:
    """
    Process and store document content received from the SurfSense Extension.

    Args:
        session: Database session
        content: Document content from extension
        search_space_id: ID of the search space

    Returns:
        Document object if successful, None if failed
    """
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

        # Generate summary
        summary_chain = SUMMARY_PROMPT_TEMPLATE | config.long_context_llm_instance
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
        raise RuntimeError(f"Failed to process extension document: {str(e)}")


async def add_received_markdown_file_document(
    session: AsyncSession, file_name: str, file_in_markdown: str, search_space_id: int
) -> Optional[Document]:
    try:
        # Generate summary
        summary_chain = SUMMARY_PROMPT_TEMPLATE | config.long_context_llm_instance
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
                "SAVED_AT": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            content=summary_content,
            embedding=summary_embedding,
            chunks=chunks,
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
        raise RuntimeError(f"Failed to process file document: {str(e)}")


async def add_received_file_document(
    session: AsyncSession,
    file_name: str,
    unstructured_processed_elements: List[LangChainDocument],
    search_space_id: int,
) -> Optional[Document]:
    try:
        file_in_markdown = await convert_document_to_markdown(
            unstructured_processed_elements
        )

        # TODO: Check if file_markdown exceeds token limit of embedding model

        # Generate summary
        summary_chain = SUMMARY_PROMPT_TEMPLATE | config.long_context_llm_instance
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
                "SAVED_AT": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            content=summary_content,
            embedding=summary_embedding,
            chunks=chunks,
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
        raise RuntimeError(f"Failed to process file document: {str(e)}")


async def add_youtube_video_document(
    session: AsyncSession, url: str, search_space_id: int
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
    try:
        # Extract video ID from URL
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

        # Get video metadata using async HTTP client
        params = {
            "format": "json",
            "url": f"https://www.youtube.com/watch?v={video_id}",
        }
        oembed_url = "https://www.youtube.com/oembed"

        async with aiohttp.ClientSession() as http_session:
            async with http_session.get(oembed_url, params=params) as response:
                video_data = await response.json()

        # Get video transcript
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
        except Exception as e:
            transcript_text = f"No captions available for this video. Error: {str(e)}"

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

        # Generate summary
        summary_chain = SUMMARY_PROMPT_TEMPLATE | config.long_context_llm_instance
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
            for chunk in config.chunker_instance.chunk(combined_document_string)
        ]

        # Create document

        document = DB_Document(
            title=video_data.get("title", "YouTube Video"),
            document_type=DB_DocumentType.YOUTUBE_VIDEO,
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
        logging.error(f"Failed to process YouTube video: {str(e)}")
        raise
