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

md = MarkdownifyTransformer()


async def add_crawled_url_document(
    session: AsyncSession,
    url: str,
    search_space_id: int
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
                }
            )
        else:
            crawl_loader = AsyncChromiumLoader(urls=[url], headless=True)

        url_crawled = await crawl_loader.aload()

        if type(crawl_loader) == FireCrawlLoader:
            content_in_markdown = url_crawled[0].page_content
        elif type(crawl_loader) == AsyncChromiumLoader:
            content_in_markdown = md.transform_documents(url_crawled)[
                0].page_content

        # Format document metadata in a more maintainable way
        metadata_sections = [
            ("METADATA", [
                f"{key.upper()}: {value}" for key, value in url_crawled[0].metadata.items()
            ]),
            ("CONTENT", [
                "FORMAT: markdown",
                "TEXT_START",
                content_in_markdown,
                "TEXT_END"
            ])
        ]

        # Build the document string more efficiently
        document_parts = []
        document_parts.append("<DOCUMENT>")

        for section_title, section_content in metadata_sections:
            document_parts.append(f"<{section_title}>")
            document_parts.extend(section_content)
            document_parts.append(f"</{section_title}>")

        document_parts.append("</DOCUMENT>")
        combined_document_string = '\n'.join(document_parts)

        # Generate summary
        summary_chain = SUMMARY_PROMPT_TEMPLATE | config.long_context_llm_instance
        summary_result = await summary_chain.ainvoke({"document": combined_document_string})
        summary_content = summary_result.content
        summary_embedding = config.embedding_model_instance.embed(
            summary_content)

        # Process chunks
        chunks = [
            Chunk(content=chunk.text, embedding=chunk.embedding)
            for chunk in config.chunker_instance.chunk(content_in_markdown)
        ]

        # Create and store document
        document = Document(
            search_space_id=search_space_id,
            title=url_crawled[0].metadata['title'] if type(
                crawl_loader) == FireCrawlLoader else url_crawled[0].metadata['source'],
            document_type=DocumentType.CRAWLED_URL,
            document_metadata=url_crawled[0].metadata,
            content=summary_content,
            embedding=summary_embedding,
            chunks=chunks
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
    session: AsyncSession,
    content: ExtensionDocumentContent,
    search_space_id: int
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
            ("METADATA", [
                f"SESSION_ID: {content.metadata.BrowsingSessionId}",
                f"URL: {content.metadata.VisitedWebPageURL}",
                f"TITLE: {content.metadata.VisitedWebPageTitle}",
                f"REFERRER: {content.metadata.VisitedWebPageReffererURL}",
                f"TIMESTAMP: {content.metadata.VisitedWebPageDateWithTimeInISOString}",
                f"DURATION_MS: {content.metadata.VisitedWebPageVisitDurationInMilliseconds}"
            ]),
            ("CONTENT", [
                "FORMAT: markdown",
                "TEXT_START",
                content.pageContent,
                "TEXT_END"
            ])
        ]

        # Build the document string more efficiently
        document_parts = []
        document_parts.append("<DOCUMENT>")

        for section_title, section_content in metadata_sections:
            document_parts.append(f"<{section_title}>")
            document_parts.extend(section_content)
            document_parts.append(f"</{section_title}>")

        document_parts.append("</DOCUMENT>")
        combined_document_string = '\n'.join(document_parts)

        # Generate summary
        summary_chain = SUMMARY_PROMPT_TEMPLATE | config.long_context_llm_instance
        summary_result = await summary_chain.ainvoke({"document": combined_document_string})
        summary_content = summary_result.content
        summary_embedding = config.embedding_model_instance.embed(
            summary_content)

        # Process chunks
        chunks = [
            Chunk(content=chunk.text, embedding=chunk.embedding)
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
            chunks=chunks
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


async def add_received_file_document(
    session: AsyncSession,
    file_name: str,
    unstructured_processed_elements: List[LangChainDocument],
    search_space_id: int
) -> Optional[Document]:
    try:
        file_in_markdown = await convert_document_to_markdown(unstructured_processed_elements)

        # TODO: Check if file_markdown exceeds token limit of embedding model

        # Generate summary
        summary_chain = SUMMARY_PROMPT_TEMPLATE | config.long_context_llm_instance
        summary_result = await summary_chain.ainvoke({"document": file_in_markdown})
        summary_content = summary_result.content
        summary_embedding = config.embedding_model_instance.embed(
            summary_content)

       # Process chunks
        chunks = [
            Chunk(content=chunk.text, embedding=chunk.embedding)
            for chunk in config.chunker_instance.chunk(file_in_markdown)
        ]

        # Create and store document
        document = Document(
            search_space_id=search_space_id,
            title=file_name,
            document_type=DocumentType.FILE,
            document_metadata={
                "FILE_NAME": file_name,
                "SAVED_AT": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            },
            content=summary_content,
            embedding=summary_embedding,
            chunks=chunks
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
