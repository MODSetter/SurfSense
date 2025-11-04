"""
Notion connector indexer.
"""

from datetime import datetime, timedelta

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.notion_history import NotionHistoryConnector
from app.db import Document, DocumentType, SearchSourceConnectorType
from app.services.llm_service import get_user_long_context_llm
from app.services.task_logging_service import TaskLoggingService
from app.utils.document_converters import (
    create_document_chunks,
    generate_content_hash,
    generate_document_summary,
    generate_unique_identifier_hash,
)

from .base import (
    build_document_metadata_string,
    check_document_by_unique_identifier,
    get_connector_by_id,
    logger,
    update_connector_last_indexed,
)


async def index_notion_pages(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    update_last_indexed: bool = True,
) -> tuple[int, str | None]:
    """
    Index Notion pages from all accessible pages.

    Args:
        session: Database session
        connector_id: ID of the Notion connector
        search_space_id: ID of the search space to store documents in
        user_id: ID of the user
        start_date: Start date for indexing (YYYY-MM-DD format)
        end_date: End date for indexing (YYYY-MM-DD format)
        update_last_indexed: Whether to update the last_indexed_at timestamp (default: True)

    Returns:
        Tuple containing (number of documents indexed, error message or None)
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="notion_pages_indexing",
        source="connector_indexing_task",
        message=f"Starting Notion pages indexing for connector {connector_id}",
        metadata={
            "connector_id": connector_id,
            "user_id": str(user_id),
            "start_date": start_date,
            "end_date": end_date,
        },
    )

    try:
        # Get the connector
        await task_logger.log_task_progress(
            log_entry,
            f"Retrieving Notion connector {connector_id} from database",
            {"stage": "connector_retrieval"},
        )

        connector = await get_connector_by_id(
            session, connector_id, SearchSourceConnectorType.NOTION_CONNECTOR
        )

        if not connector:
            await task_logger.log_task_failure(
                log_entry,
                f"Connector with ID {connector_id} not found or is not a Notion connector",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return (
                0,
                f"Connector with ID {connector_id} not found or is not a Notion connector",
            )

        # Get the Notion token from the connector config
        notion_token = connector.config.get("NOTION_INTEGRATION_TOKEN")
        if not notion_token:
            await task_logger.log_task_failure(
                log_entry,
                f"Notion integration token not found in connector config for connector {connector_id}",
                "Missing Notion token",
                {"error_type": "MissingToken"},
            )
            return 0, "Notion integration token not found in connector config"

        # Initialize Notion client
        await task_logger.log_task_progress(
            log_entry,
            f"Initializing Notion client for connector {connector_id}",
            {"stage": "client_initialization"},
        )

        logger.info(f"Initializing Notion client for connector {connector_id}")

        # Calculate date range
        if start_date is None or end_date is None:
            # Fall back to calculating dates
            calculated_end_date = datetime.now()
            calculated_start_date = calculated_end_date - timedelta(
                days=365
            )  # Check for last 1 year of pages

            # Use calculated dates if not provided
            if start_date is None:
                start_date_iso = calculated_start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            else:
                # Convert YYYY-MM-DD to ISO format
                start_date_iso = datetime.strptime(start_date, "%Y-%m-%d").strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )

            if end_date is None:
                end_date_iso = calculated_end_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            else:
                # Convert YYYY-MM-DD to ISO format
                end_date_iso = datetime.strptime(end_date, "%Y-%m-%d").strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
        else:
            # Convert provided dates to ISO format for Notion API
            start_date_iso = datetime.strptime(start_date, "%Y-%m-%d").strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            end_date_iso = datetime.strptime(end_date, "%Y-%m-%d").strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )

        notion_client = NotionHistoryConnector(token=notion_token)

        logger.info(f"Fetching Notion pages from {start_date_iso} to {end_date_iso}")

        await task_logger.log_task_progress(
            log_entry,
            f"Fetching Notion pages from {start_date_iso} to {end_date_iso}",
            {
                "stage": "fetch_pages",
                "start_date": start_date_iso,
                "end_date": end_date_iso,
            },
        )

        # Get all pages
        try:
            pages = await notion_client.get_all_pages(
                start_date=start_date_iso, end_date=end_date_iso
            )
            logger.info(f"Found {len(pages)} Notion pages")
        except Exception as e:
            await task_logger.log_task_failure(
                log_entry,
                f"Failed to get Notion pages for connector {connector_id}",
                str(e),
                {"error_type": "PageFetchError"},
            )
            logger.error(f"Error fetching Notion pages: {e!s}", exc_info=True)
            await notion_client.close()
            return 0, f"Failed to get Notion pages: {e!s}"

        if not pages:
            await task_logger.log_task_success(
                log_entry,
                f"No Notion pages found for connector {connector_id}",
                {"pages_found": 0},
            )
            logger.info("No Notion pages found to index")
            await notion_client.close()
            return 0, "No Notion pages found"

        # Track the number of documents indexed
        documents_indexed = 0
        documents_skipped = 0
        skipped_pages = []

        await task_logger.log_task_progress(
            log_entry,
            f"Starting to process {len(pages)} Notion pages",
            {"stage": "process_pages", "total_pages": len(pages)},
        )

        # Process each page
        for page in pages:
            try:
                page_id = page.get("page_id")
                page_title = page.get("title", f"Untitled page ({page_id})")
                page_content = page.get("content", [])

                logger.info(f"Processing Notion page: {page_title} ({page_id})")

                if not page_content:
                    logger.info(f"No content found in page {page_title}. Skipping.")
                    skipped_pages.append(f"{page_title} (no content)")
                    documents_skipped += 1
                    continue

                # Convert page content to markdown format
                markdown_content = f"# Notion Page: {page_title}\n\n"

                # Process blocks recursively
                def process_blocks(blocks, level=0):
                    result = ""
                    for block in blocks:
                        block_type = block.get("type")
                        block_content = block.get("content", "")
                        children = block.get("children", [])

                        # Add indentation based on level
                        indent = "  " * level

                        # Format based on block type
                        if block_type in ["paragraph", "text"]:
                            result += f"{indent}{block_content}\n\n"
                        elif block_type in ["heading_1", "header"]:
                            result += f"{indent}# {block_content}\n\n"
                        elif block_type == "heading_2":
                            result += f"{indent}## {block_content}\n\n"
                        elif block_type == "heading_3":
                            result += f"{indent}### {block_content}\n\n"
                        elif block_type == "bulleted_list_item":
                            result += f"{indent}* {block_content}\n"
                        elif block_type == "numbered_list_item":
                            result += f"{indent}1. {block_content}\n"
                        elif block_type == "to_do":
                            result += f"{indent}- [ ] {block_content}\n"
                        elif block_type == "toggle":
                            result += f"{indent}> {block_content}\n"
                        elif block_type == "code":
                            result += f"{indent}```\n{block_content}\n```\n\n"
                        elif block_type == "quote":
                            result += f"{indent}> {block_content}\n\n"
                        elif block_type == "callout":
                            result += f"{indent}> **Note:** {block_content}\n\n"
                        elif block_type == "image":
                            result += f"{indent}![Image]({block_content})\n\n"
                        else:
                            # Default for other block types
                            if block_content:
                                result += f"{indent}{block_content}\n\n"

                        # Process children recursively
                        if children:
                            result += process_blocks(children, level + 1)

                    return result

                logger.debug(
                    f"Converting {len(page_content)} blocks to markdown for page {page_title}"
                )
                markdown_content += process_blocks(page_content)

                # Format document metadata
                metadata_sections = [
                    ("METADATA", [f"PAGE_TITLE: {page_title}", f"PAGE_ID: {page_id}"]),
                    (
                        "CONTENT",
                        [
                            "FORMAT: markdown",
                            "TEXT_START",
                            markdown_content,
                            "TEXT_END",
                        ],
                    ),
                ]

                # Build the document string
                combined_document_string = build_document_metadata_string(
                    metadata_sections
                )

                # Generate unique identifier hash for this Notion page
                unique_identifier_hash = generate_unique_identifier_hash(
                    DocumentType.NOTION_CONNECTOR, page_id, search_space_id
                )

                # Generate content hash
                content_hash = generate_content_hash(
                    combined_document_string, search_space_id
                )

                # Check if document with this unique identifier already exists
                existing_document = await check_document_by_unique_identifier(
                    session, unique_identifier_hash
                )

                if existing_document:
                    # Document exists - check if content has changed
                    if existing_document.content_hash == content_hash:
                        logger.info(
                            f"Document for Notion page {page_title} unchanged. Skipping."
                        )
                        documents_skipped += 1
                        continue
                    else:
                        # Content has changed - update the existing document
                        logger.info(
                            f"Content changed for Notion page {page_title}. Updating document."
                        )

                        # Get user's long context LLM
                        user_llm = await get_user_long_context_llm(
                            session, user_id, search_space_id
                        )
                        if not user_llm:
                            logger.error(
                                f"No long context LLM configured for user {user_id}"
                            )
                            skipped_pages.append(f"{page_title} (no LLM configured)")
                            documents_skipped += 1
                            continue

                        # Generate summary with metadata
                        document_metadata = {
                            "page_title": page_title,
                            "page_id": page_id,
                            "document_type": "Notion Page",
                            "connector_type": "Notion",
                        }
                        (
                            summary_content,
                            summary_embedding,
                        ) = await generate_document_summary(
                            markdown_content, user_llm, document_metadata
                        )

                        # Process chunks
                        chunks = await create_document_chunks(markdown_content)

                        # Update existing document
                        existing_document.title = f"Notion - {page_title}"
                        existing_document.content = summary_content
                        existing_document.content_hash = content_hash
                        existing_document.embedding = summary_embedding
                        existing_document.document_metadata = {
                            "page_title": page_title,
                            "page_id": page_id,
                            "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        }
                        existing_document.chunks = chunks

                        documents_indexed += 1
                        logger.info(f"Successfully updated Notion page: {page_title}")

                        # Batch commit every 10 documents
                        if documents_indexed % 10 == 0:
                            logger.info(
                                f"Committing batch: {documents_indexed} documents processed so far"
                            )
                            await session.commit()

                        continue

                # Document doesn't exist - create new one
                # Get user's long context LLM
                user_llm = await get_user_long_context_llm(
                    session, user_id, search_space_id
                )
                if not user_llm:
                    logger.error(f"No long context LLM configured for user {user_id}")
                    skipped_pages.append(f"{page_title} (no LLM configured)")
                    documents_skipped += 1
                    continue

                # Generate summary with metadata
                logger.debug(f"Generating summary for page {page_title}")
                document_metadata = {
                    "page_title": page_title,
                    "page_id": page_id,
                    "document_type": "Notion Page",
                    "connector_type": "Notion",
                }
                summary_content, summary_embedding = await generate_document_summary(
                    markdown_content, user_llm, document_metadata
                )

                # Process chunks
                logger.debug(f"Chunking content for page {page_title}")
                chunks = await create_document_chunks(markdown_content)

                # Create and store new document
                document = Document(
                    search_space_id=search_space_id,
                    title=f"Notion - {page_title}",
                    document_type=DocumentType.NOTION_CONNECTOR,
                    document_metadata={
                        "page_title": page_title,
                        "page_id": page_id,
                        "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    },
                    content=summary_content,
                    content_hash=content_hash,
                    unique_identifier_hash=unique_identifier_hash,
                    embedding=summary_embedding,
                    chunks=chunks,
                )

                session.add(document)
                documents_indexed += 1
                logger.info(f"Successfully indexed new Notion page: {page_title}")

                # Batch commit every 10 documents
                if documents_indexed % 10 == 0:
                    logger.info(
                        f"Committing batch: {documents_indexed} documents processed so far"
                    )
                    await session.commit()

            except Exception as e:
                logger.error(
                    f"Error processing Notion page {page.get('title', 'Unknown')}: {e!s}",
                    exc_info=True,
                )
                skipped_pages.append(
                    f"{page.get('title', 'Unknown')} (processing error)"
                )
                documents_skipped += 1
                continue  # Skip this page and continue with others

        # Update the last_indexed_at timestamp for the connector only if requested
        # and if we successfully indexed at least one page
        total_processed = documents_indexed
        if total_processed > 0:
            await update_connector_last_indexed(session, connector, update_last_indexed)

        # Final commit for any remaining documents not yet committed in batches
        logger.info(f"Final commit: Total {documents_indexed} documents processed")
        await session.commit()

        # Prepare result message
        result_message = None
        if skipped_pages:
            result_message = f"Processed {total_processed} pages. Skipped {len(skipped_pages)} pages: {', '.join(skipped_pages)}"
        else:
            result_message = f"Processed {total_processed} pages."

        # Log success
        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed Notion indexing for connector {connector_id}",
            {
                "pages_processed": total_processed,
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
                "skipped_pages_count": len(skipped_pages),
                "result_message": result_message,
            },
        )

        logger.info(
            f"Notion indexing completed: {documents_indexed} new pages, {documents_skipped} skipped"
        )

        # Clean up the async client
        await notion_client.close()

        return total_processed, result_message

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during Notion indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(
            f"Database error during Notion indexing: {db_error!s}", exc_info=True
        )
        # Clean up the async client in case of error
        if "notion_client" in locals():
            await notion_client.close()
        return 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index Notion pages for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index Notion pages: {e!s}", exc_info=True)
        # Clean up the async client in case of error
        if "notion_client" in locals():
            await notion_client.close()
        return 0, f"Failed to index Notion pages: {e!s}"
