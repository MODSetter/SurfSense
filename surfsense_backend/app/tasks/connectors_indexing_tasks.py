import asyncio
import logging
from datetime import UTC, datetime, timedelta

from slack_sdk.errors import SlackApiError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import config
from app.connectors.confluence_connector import ConfluenceConnector
from app.connectors.discord_connector import DiscordConnector
from app.connectors.github_connector import GitHubConnector
from app.connectors.jira_connector import JiraConnector
from app.connectors.linear_connector import LinearConnector
from app.connectors.notion_history import NotionHistoryConnector
from app.connectors.slack_history import SlackHistory
from app.db import (
    Chunk,
    Document,
    DocumentType,
    SearchSourceConnector,
    SearchSourceConnectorType,
)
from app.prompts import SUMMARY_PROMPT_TEMPLATE
from app.services.llm_service import get_user_long_context_llm
from app.services.task_logging_service import TaskLoggingService
from app.utils.document_converters import generate_content_hash

# Set up logging
logger = logging.getLogger(__name__)


async def index_slack_messages(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    update_last_indexed: bool = True,
) -> tuple[int, str | None]:
    """
    Index Slack messages from all accessible channels.

    Args:
        session: Database session
        connector_id: ID of the Slack connector
        search_space_id: ID of the search space to store documents in
        update_last_indexed: Whether to update the last_indexed_at timestamp (default: True)

    Returns:
        Tuple containing (number of documents indexed, error message or None)
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="slack_messages_indexing",
        source="connector_indexing_task",
        message=f"Starting Slack messages indexing for connector {connector_id}",
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
            f"Retrieving Slack connector {connector_id} from database",
            {"stage": "connector_retrieval"},
        )

        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.SLACK_CONNECTOR,
            )
        )
        connector = result.scalars().first()

        if not connector:
            await task_logger.log_task_failure(
                log_entry,
                f"Connector with ID {connector_id} not found or is not a Slack connector",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return (
                0,
                f"Connector with ID {connector_id} not found or is not a Slack connector",
            )

        # Get the Slack token from the connector config
        slack_token = connector.config.get("SLACK_BOT_TOKEN")
        if not slack_token:
            await task_logger.log_task_failure(
                log_entry,
                f"Slack token not found in connector config for connector {connector_id}",
                "Missing Slack token",
                {"error_type": "MissingToken"},
            )
            return 0, "Slack token not found in connector config"

        # Initialize Slack client
        await task_logger.log_task_progress(
            log_entry,
            f"Initializing Slack client for connector {connector_id}",
            {"stage": "client_initialization"},
        )

        slack_client = SlackHistory(token=slack_token)

        # Calculate date range
        await task_logger.log_task_progress(
            log_entry,
            "Calculating date range for Slack indexing",
            {
                "stage": "date_calculation",
                "provided_start_date": start_date,
                "provided_end_date": end_date,
            },
        )

        if start_date is None or end_date is None:
            # Fall back to calculating dates based on last_indexed_at
            calculated_end_date = datetime.now()

            # Use last_indexed_at as start date if available, otherwise use 365 days ago
            if connector.last_indexed_at:
                # Convert dates to be comparable (both timezone-naive)
                last_indexed_naive = (
                    connector.last_indexed_at.replace(tzinfo=None)
                    if connector.last_indexed_at.tzinfo
                    else connector.last_indexed_at
                )

                # Check if last_indexed_at is in the future or after end_date
                if last_indexed_naive > calculated_end_date:
                    logger.warning(
                        f"Last indexed date ({last_indexed_naive.strftime('%Y-%m-%d')}) is in the future. Using 365 days ago instead."
                    )
                    calculated_start_date = calculated_end_date - timedelta(days=365)
                else:
                    calculated_start_date = last_indexed_naive
                    logger.info(
                        f"Using last_indexed_at ({calculated_start_date.strftime('%Y-%m-%d')}) as start date"
                    )
            else:
                calculated_start_date = calculated_end_date - timedelta(
                    days=365
                )  # Use 365 days as default
                logger.info(
                    f"No last_indexed_at found, using {calculated_start_date.strftime('%Y-%m-%d')} (365 days ago) as start date"
                )

            # Use calculated dates if not provided
            start_date_str = (
                start_date if start_date else calculated_start_date.strftime("%Y-%m-%d")
            )
            end_date_str = (
                end_date if end_date else calculated_end_date.strftime("%Y-%m-%d")
            )
        else:
            # Use provided dates
            start_date_str = start_date
            end_date_str = end_date

        logger.info(f"Indexing Slack messages from {start_date_str} to {end_date_str}")

        await task_logger.log_task_progress(
            log_entry,
            f"Fetching Slack channels from {start_date_str} to {end_date_str}",
            {
                "stage": "fetch_channels",
                "start_date": start_date_str,
                "end_date": end_date_str,
            },
        )

        # Get all channels
        try:
            channels = slack_client.get_all_channels()
        except Exception as e:
            await task_logger.log_task_failure(
                log_entry,
                f"Failed to get Slack channels for connector {connector_id}",
                str(e),
                {"error_type": "ChannelFetchError"},
            )
            return 0, f"Failed to get Slack channels: {e!s}"

        if not channels:
            await task_logger.log_task_success(
                log_entry,
                f"No Slack channels found for connector {connector_id}",
                {"channels_found": 0},
            )
            return 0, "No Slack channels found"

        # Track the number of documents indexed
        documents_indexed = 0
        documents_skipped = 0
        skipped_channels = []

        await task_logger.log_task_progress(
            log_entry,
            f"Starting to process {len(channels)} Slack channels",
            {"stage": "process_channels", "total_channels": len(channels)},
        )

        # Process each channel
        for (
            channel_obj
        ) in channels:  # Modified loop to iterate over list of channel objects
            channel_id = channel_obj["id"]
            channel_name = channel_obj["name"]
            is_private = channel_obj["is_private"]
            is_member = channel_obj[
                "is_member"
            ]  # This might be False for public channels too

            try:
                # If it's a private channel and the bot is not a member, skip.
                # For public channels, if they are listed by conversations.list, the bot can typically read history.
                # The `not_in_channel` error in get_conversation_history will be the ultimate gatekeeper if history is inaccessible.
                if is_private and not is_member:
                    logger.warning(
                        f"Bot is not a member of private channel {channel_name} ({channel_id}). Skipping."
                    )
                    skipped_channels.append(
                        f"{channel_name} (private, bot not a member)"
                    )
                    documents_skipped += 1
                    continue

                # Get messages for this channel
                # The get_history_by_date_range now uses get_conversation_history,
                # which handles 'not_in_channel' by returning [] and logging.
                messages, error = slack_client.get_history_by_date_range(
                    channel_id=channel_id,
                    start_date=start_date_str,
                    end_date=end_date_str,
                    limit=1000,  # Limit to 1000 messages per channel
                )

                if error:
                    logger.warning(
                        f"Error getting messages from channel {channel_name}: {error}"
                    )
                    skipped_channels.append(f"{channel_name} (error: {error})")
                    documents_skipped += 1
                    continue  # Skip this channel if there's an error

                if not messages:
                    logger.info(
                        f"No messages found in channel {channel_name} for the specified date range."
                    )
                    documents_skipped += 1
                    continue  # Skip if no messages

                # Format messages with user info
                formatted_messages = []
                for msg in messages:
                    # Skip bot messages and system messages
                    if msg.get("subtype") in [
                        "bot_message",
                        "channel_join",
                        "channel_leave",
                    ]:
                        continue

                    formatted_msg = slack_client.format_message(
                        msg, include_user_info=True
                    )
                    formatted_messages.append(formatted_msg)

                if not formatted_messages:
                    logger.info(
                        f"No valid messages found in channel {channel_name} after filtering."
                    )
                    documents_skipped += 1
                    continue  # Skip if no valid messages after filtering

                # Convert messages to markdown format
                channel_content = f"# Slack Channel: {channel_name}\n\n"

                for msg in formatted_messages:
                    user_name = msg.get("user_name", "Unknown User")
                    timestamp = msg.get("datetime", "Unknown Time")
                    text = msg.get("text", "")

                    channel_content += (
                        f"## {user_name} ({timestamp})\n\n{text}\n\n---\n\n"
                    )

                # Format document metadata
                metadata_sections = [
                    (
                        "METADATA",
                        [
                            f"CHANNEL_NAME: {channel_name}",
                            f"CHANNEL_ID: {channel_id}",
                            # f"START_DATE: {start_date_str}",
                            # f"END_DATE: {end_date_str}",
                            f"MESSAGE_COUNT: {len(formatted_messages)}",
                        ],
                    ),
                    (
                        "CONTENT",
                        ["FORMAT: markdown", "TEXT_START", channel_content, "TEXT_END"],
                    ),
                ]

                # Build the document string
                document_parts = []
                document_parts.append("<DOCUMENT>")

                for section_title, section_content in metadata_sections:
                    document_parts.append(f"<{section_title}>")
                    document_parts.extend(section_content)
                    document_parts.append(f"</{section_title}>")

                document_parts.append("</DOCUMENT>")
                combined_document_string = "\n".join(document_parts)
                content_hash = generate_content_hash(
                    combined_document_string, search_space_id
                )

                # Check if document with this content hash already exists
                existing_doc_by_hash_result = await session.execute(
                    select(Document).where(Document.content_hash == content_hash)
                )
                existing_document_by_hash = (
                    existing_doc_by_hash_result.scalars().first()
                )

                if existing_document_by_hash:
                    logger.info(
                        f"Document with content hash {content_hash} already exists for channel {channel_name}. Skipping processing."
                    )
                    documents_skipped += 1
                    continue

                # Get user's long context LLM
                user_llm = await get_user_long_context_llm(session, user_id)
                if not user_llm:
                    logger.error(f"No long context LLM configured for user {user_id}")
                    skipped_channels.append(f"{channel_name} (no LLM configured)")
                    documents_skipped += 1
                    continue

                # Generate summary
                summary_chain = SUMMARY_PROMPT_TEMPLATE | user_llm
                summary_result = await summary_chain.ainvoke(
                    {"document": combined_document_string}
                )
                summary_content = summary_result.content
                summary_embedding = config.embedding_model_instance.embed(
                    summary_content
                )

                # Process chunks
                chunks = [
                    Chunk(
                        content=chunk.text,
                        embedding=config.embedding_model_instance.embed(chunk.text),
                    )
                    for chunk in config.chunker_instance.chunk(channel_content)
                ]

                # Create and store new document
                document = Document(
                    search_space_id=search_space_id,
                    title=f"Slack - {channel_name}",
                    document_type=DocumentType.SLACK_CONNECTOR,
                    document_metadata={
                        "channel_name": channel_name,
                        "channel_id": channel_id,
                        "start_date": start_date_str,
                        "end_date": end_date_str,
                        "message_count": len(formatted_messages),
                        "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    },
                    content=summary_content,
                    embedding=summary_embedding,
                    chunks=chunks,
                    content_hash=content_hash,
                )

                session.add(document)
                documents_indexed += 1
                logger.info(
                    f"Successfully indexed new channel {channel_name} with {len(formatted_messages)} messages"
                )

            except SlackApiError as slack_error:
                logger.error(
                    f"Slack API error for channel {channel_name}: {slack_error!s}"
                )
                skipped_channels.append(f"{channel_name} (Slack API error)")
                documents_skipped += 1
                continue  # Skip this channel and continue with others
            except Exception as e:
                logger.error(f"Error processing channel {channel_name}: {e!s}")
                skipped_channels.append(f"{channel_name} (processing error)")
                documents_skipped += 1
                continue  # Skip this channel and continue with others

        # Update the last_indexed_at timestamp for the connector only if requested
        # and if we successfully indexed at least one channel
        total_processed = documents_indexed
        if update_last_indexed and total_processed > 0:
            connector.last_indexed_at = datetime.now()

        # Commit all changes
        await session.commit()

        # Prepare result message
        result_message = None
        if skipped_channels:
            result_message = f"Processed {total_processed} channels. Skipped {len(skipped_channels)} channels: {', '.join(skipped_channels)}"
        else:
            result_message = f"Processed {total_processed} channels."

        # Log success
        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed Slack indexing for connector {connector_id}",
            {
                "channels_processed": total_processed,
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
                "skipped_channels_count": len(skipped_channels),
                "result_message": result_message,
            },
        )

        logger.info(
            f"Slack indexing completed: {documents_indexed} new channels, {documents_skipped} skipped"
        )
        return total_processed, result_message

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during Slack indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(f"Database error: {db_error!s}")
        return 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index Slack messages for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index Slack messages: {e!s}")
        return 0, f"Failed to index Slack messages: {e!s}"


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

        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.NOTION_CONNECTOR,
            )
        )
        connector = result.scalars().first()

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
        notion_client = NotionHistoryConnector(token=notion_token)

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
            pages = notion_client.get_all_pages(
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
            return 0, f"Failed to get Notion pages: {e!s}"

        if not pages:
            await task_logger.log_task_success(
                log_entry,
                f"No Notion pages found for connector {connector_id}",
                {"pages_found": 0},
            )
            logger.info("No Notion pages found to index")
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
                document_parts = []
                document_parts.append("<DOCUMENT>")

                for section_title, section_content in metadata_sections:
                    document_parts.append(f"<{section_title}>")
                    document_parts.extend(section_content)
                    document_parts.append(f"</{section_title}>")

                document_parts.append("</DOCUMENT>")
                combined_document_string = "\n".join(document_parts)
                content_hash = generate_content_hash(
                    combined_document_string, search_space_id
                )

                # Check if document with this content hash already exists
                existing_doc_by_hash_result = await session.execute(
                    select(Document).where(Document.content_hash == content_hash)
                )
                existing_document_by_hash = (
                    existing_doc_by_hash_result.scalars().first()
                )

                if existing_document_by_hash:
                    logger.info(
                        f"Document with content hash {content_hash} already exists for page {page_title}. Skipping processing."
                    )
                    documents_skipped += 1
                    continue

                # Get user's long context LLM
                user_llm = await get_user_long_context_llm(session, user_id)
                if not user_llm:
                    logger.error(f"No long context LLM configured for user {user_id}")
                    skipped_pages.append(f"{page_title} (no LLM configured)")
                    documents_skipped += 1
                    continue

                # Generate summary
                logger.debug(f"Generating summary for page {page_title}")
                summary_chain = SUMMARY_PROMPT_TEMPLATE | user_llm
                summary_result = await summary_chain.ainvoke(
                    {"document": combined_document_string}
                )
                summary_content = summary_result.content
                summary_embedding = config.embedding_model_instance.embed(
                    summary_content
                )

                # Process chunks
                logger.debug(f"Chunking content for page {page_title}")
                chunks = [
                    Chunk(
                        content=chunk.text,
                        embedding=config.embedding_model_instance.embed(chunk.text),
                    )
                    for chunk in config.chunker_instance.chunk(markdown_content)
                ]

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
                    embedding=summary_embedding,
                    chunks=chunks,
                )

                session.add(document)
                documents_indexed += 1
                logger.info(f"Successfully indexed new Notion page: {page_title}")

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
        if update_last_indexed and total_processed > 0:
            connector.last_indexed_at = datetime.now()
            logger.info(f"Updated last_indexed_at for connector {connector_id}")

        # Commit all changes
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
        return 0, f"Failed to index Notion pages: {e!s}"


async def index_github_repos(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    update_last_indexed: bool = True,
) -> tuple[int, str | None]:
    """
    Index code and documentation files from accessible GitHub repositories.

    Args:
        session: Database session
        connector_id: ID of the GitHub connector
        search_space_id: ID of the search space to store documents in
        update_last_indexed: Whether to update the last_indexed_at timestamp (default: True)

    Returns:
        Tuple containing (number of documents indexed, error message or None)
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="github_repos_indexing",
        source="connector_indexing_task",
        message=f"Starting GitHub repositories indexing for connector {connector_id}",
        metadata={
            "connector_id": connector_id,
            "user_id": str(user_id),
            "start_date": start_date,
            "end_date": end_date,
        },
    )

    documents_processed = 0
    errors = []

    try:
        # 1. Get the GitHub connector from the database
        await task_logger.log_task_progress(
            log_entry,
            f"Retrieving GitHub connector {connector_id} from database",
            {"stage": "connector_retrieval"},
        )

        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.GITHUB_CONNECTOR,
            )
        )
        connector = result.scalars().first()

        if not connector:
            await task_logger.log_task_failure(
                log_entry,
                f"Connector with ID {connector_id} not found or is not a GitHub connector",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return (
                0,
                f"Connector with ID {connector_id} not found or is not a GitHub connector",
            )

        # 2. Get the GitHub PAT and selected repositories from the connector config
        github_pat = connector.config.get("GITHUB_PAT")
        repo_full_names_to_index = connector.config.get("repo_full_names")

        if not github_pat:
            await task_logger.log_task_failure(
                log_entry,
                f"GitHub Personal Access Token (PAT) not found in connector config for connector {connector_id}",
                "Missing GitHub PAT",
                {"error_type": "MissingToken"},
            )
            return 0, "GitHub Personal Access Token (PAT) not found in connector config"

        if not repo_full_names_to_index or not isinstance(
            repo_full_names_to_index, list
        ):
            await task_logger.log_task_failure(
                log_entry,
                f"'repo_full_names' not found or is not a list in connector config for connector {connector_id}",
                "Invalid repo configuration",
                {"error_type": "InvalidConfiguration"},
            )
            return 0, "'repo_full_names' not found or is not a list in connector config"

        # 3. Initialize GitHub connector client
        await task_logger.log_task_progress(
            log_entry,
            f"Initializing GitHub client for connector {connector_id}",
            {
                "stage": "client_initialization",
                "repo_count": len(repo_full_names_to_index),
            },
        )

        try:
            github_client = GitHubConnector(token=github_pat)
        except ValueError as e:
            await task_logger.log_task_failure(
                log_entry,
                f"Failed to initialize GitHub client for connector {connector_id}",
                str(e),
                {"error_type": "ClientInitializationError"},
            )
            return 0, f"Failed to initialize GitHub client: {e!s}"

        # 4. Validate selected repositories
        #    For simplicity, we'll proceed with the list provided.
        #    If a repo is inaccessible, get_repository_files will likely fail gracefully later.
        await task_logger.log_task_progress(
            log_entry,
            f"Starting indexing for {len(repo_full_names_to_index)} selected repositories",
            {
                "stage": "repo_processing",
                "repo_count": len(repo_full_names_to_index),
                "start_date": start_date,
                "end_date": end_date,
            },
        )

        logger.info(
            f"Starting indexing for {len(repo_full_names_to_index)} selected repositories."
        )
        if start_date and end_date:
            logger.info(
                f"Date range requested: {start_date} to {end_date} (Note: GitHub indexing processes all files regardless of dates)"
            )

        # 6. Iterate through selected repositories and index files
        for repo_full_name in repo_full_names_to_index:
            if not repo_full_name or not isinstance(repo_full_name, str):
                logger.warning(f"Skipping invalid repository entry: {repo_full_name}")
                continue

            logger.info(f"Processing repository: {repo_full_name}")
            try:
                files_to_index = github_client.get_repository_files(repo_full_name)
                if not files_to_index:
                    logger.info(
                        f"No indexable files found in repository: {repo_full_name}"
                    )
                    continue

                logger.info(
                    f"Found {len(files_to_index)} files to process in {repo_full_name}"
                )

                for file_info in files_to_index:
                    file_path = file_info.get("path")
                    file_url = file_info.get("url")
                    file_sha = file_info.get("sha")
                    file_type = file_info.get("type")  # 'code' or 'doc'
                    full_path_key = f"{repo_full_name}/{file_path}"

                    if not file_path or not file_url or not file_sha:
                        logger.warning(
                            f"Skipping file with missing info in {repo_full_name}: {file_info}"
                        )
                        continue

                    # Get file content
                    file_content = github_client.get_file_content(
                        repo_full_name, file_path
                    )

                    if file_content is None:
                        logger.warning(
                            f"Could not retrieve content for {full_path_key}. Skipping."
                        )
                        continue  # Skip if content fetch failed

                    content_hash = generate_content_hash(file_content, search_space_id)

                    # Check if document with this content hash already exists
                    existing_doc_by_hash_result = await session.execute(
                        select(Document).where(Document.content_hash == content_hash)
                    )
                    existing_document_by_hash = (
                        existing_doc_by_hash_result.scalars().first()
                    )

                    if existing_document_by_hash:
                        logger.info(
                            f"Document with content hash {content_hash} already exists for file {full_path_key}. Skipping processing."
                        )
                        continue

                    # Use file_content directly for chunking, maybe summary for main content?
                    # For now, let's use the full content for both, might need refinement
                    summary_content = f"GitHub file: {full_path_key}\n\n{file_content[:1000]}..."  # Simple summary
                    summary_embedding = config.embedding_model_instance.embed(
                        summary_content
                    )

                    # Chunk the content
                    try:
                        chunks_data = [
                            Chunk(
                                content=chunk.text,
                                embedding=config.embedding_model_instance.embed(
                                    chunk.text
                                ),
                            )
                            for chunk in config.code_chunker_instance.chunk(
                                file_content
                            )
                        ]
                    except Exception as chunk_err:
                        logger.error(
                            f"Failed to chunk file {full_path_key}: {chunk_err}"
                        )
                        errors.append(
                            f"Chunking failed for {full_path_key}: {chunk_err}"
                        )
                        continue  # Skip this file if chunking fails

                    doc_metadata = {
                        "repository_full_name": repo_full_name,
                        "file_path": file_path,
                        "full_path": full_path_key,  # For easier lookup
                        "url": file_url,
                        "sha": file_sha,
                        "type": file_type,
                        "indexed_at": datetime.now(UTC).isoformat(),
                    }

                    # Create new document
                    logger.info(f"Creating new document for file: {full_path_key}")
                    document = Document(
                        title=f"GitHub - {file_path}",
                        document_type=DocumentType.GITHUB_CONNECTOR,
                        document_metadata=doc_metadata,
                        content=summary_content,  # Store summary
                        content_hash=content_hash,
                        embedding=summary_embedding,
                        search_space_id=search_space_id,
                        chunks=chunks_data,  # Associate chunks directly
                    )
                    session.add(document)
                    documents_processed += 1

            except Exception as repo_err:
                logger.error(
                    f"Failed to process repository {repo_full_name}: {repo_err}"
                )
                errors.append(f"Failed processing {repo_full_name}: {repo_err}")

        # Commit all changes at the end
        await session.commit()
        logger.info(
            f"Finished GitHub indexing for connector {connector_id}. Processed {documents_processed} files."
        )

        # Log success
        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed GitHub indexing for connector {connector_id}",
            {
                "documents_processed": documents_processed,
                "errors_count": len(errors),
                "repo_count": len(repo_full_names_to_index),
            },
        )

    except SQLAlchemyError as db_err:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during GitHub indexing for connector {connector_id}",
            str(db_err),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(
            f"Database error during GitHub indexing for connector {connector_id}: {db_err}"
        )
        errors.append(f"Database error: {db_err}")
        return documents_processed, "; ".join(errors) if errors else str(db_err)
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Unexpected error during GitHub indexing for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(
            f"Unexpected error during GitHub indexing for connector {connector_id}: {e}",
            exc_info=True,
        )
        errors.append(f"Unexpected error: {e}")
        return documents_processed, "; ".join(errors) if errors else str(e)

    error_message = "; ".join(errors) if errors else None
    return documents_processed, error_message


async def index_linear_issues(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    update_last_indexed: bool = True,
) -> tuple[int, str | None]:
    """
    Index Linear issues and comments.

    Args:
        session: Database session
        connector_id: ID of the Linear connector
        search_space_id: ID of the search space to store documents in
        update_last_indexed: Whether to update the last_indexed_at timestamp (default: True)

    Returns:
        Tuple containing (number of documents indexed, error message or None)
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="linear_issues_indexing",
        source="connector_indexing_task",
        message=f"Starting Linear issues indexing for connector {connector_id}",
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
            f"Retrieving Linear connector {connector_id} from database",
            {"stage": "connector_retrieval"},
        )

        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.LINEAR_CONNECTOR,
            )
        )
        connector = result.scalars().first()

        if not connector:
            await task_logger.log_task_failure(
                log_entry,
                f"Connector with ID {connector_id} not found or is not a Linear connector",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return (
                0,
                f"Connector with ID {connector_id} not found or is not a Linear connector",
            )

        # Get the Linear token from the connector config
        linear_token = connector.config.get("LINEAR_API_KEY")
        if not linear_token:
            await task_logger.log_task_failure(
                log_entry,
                f"Linear API token not found in connector config for connector {connector_id}",
                "Missing Linear token",
                {"error_type": "MissingToken"},
            )
            return 0, "Linear API token not found in connector config"

        # Initialize Linear client
        await task_logger.log_task_progress(
            log_entry,
            f"Initializing Linear client for connector {connector_id}",
            {"stage": "client_initialization"},
        )

        linear_client = LinearConnector(token=linear_token)

        # Calculate date range
        if start_date is None or end_date is None:
            # Fall back to calculating dates based on last_indexed_at
            calculated_end_date = datetime.now()

            # Use last_indexed_at as start date if available, otherwise use 365 days ago
            if connector.last_indexed_at:
                # Convert dates to be comparable (both timezone-naive)
                last_indexed_naive = (
                    connector.last_indexed_at.replace(tzinfo=None)
                    if connector.last_indexed_at.tzinfo
                    else connector.last_indexed_at
                )

                # Check if last_indexed_at is in the future or after end_date
                if last_indexed_naive > calculated_end_date:
                    logger.warning(
                        f"Last indexed date ({last_indexed_naive.strftime('%Y-%m-%d')}) is in the future. Using 365 days ago instead."
                    )
                    calculated_start_date = calculated_end_date - timedelta(days=365)
                else:
                    calculated_start_date = last_indexed_naive
                    logger.info(
                        f"Using last_indexed_at ({calculated_start_date.strftime('%Y-%m-%d')}) as start date"
                    )
            else:
                calculated_start_date = calculated_end_date - timedelta(
                    days=365
                )  # Use 365 days as default
                logger.info(
                    f"No last_indexed_at found, using {calculated_start_date.strftime('%Y-%m-%d')} (365 days ago) as start date"
                )

            # Use calculated dates if not provided
            start_date_str = (
                start_date if start_date else calculated_start_date.strftime("%Y-%m-%d")
            )
            end_date_str = (
                end_date if end_date else calculated_end_date.strftime("%Y-%m-%d")
            )
        else:
            # Use provided dates
            start_date_str = start_date
            end_date_str = end_date

        logger.info(f"Fetching Linear issues from {start_date_str} to {end_date_str}")

        await task_logger.log_task_progress(
            log_entry,
            f"Fetching Linear issues from {start_date_str} to {end_date_str}",
            {
                "stage": "fetch_issues",
                "start_date": start_date_str,
                "end_date": end_date_str,
            },
        )

        # Get issues within date range
        try:
            issues, error = linear_client.get_issues_by_date_range(
                start_date=start_date_str, end_date=end_date_str, include_comments=True
            )

            if error:
                logger.error(f"Failed to get Linear issues: {error}")

                # Don't treat "No issues found" as an error that should stop indexing
                if "No issues found" in error:
                    logger.info(
                        "No issues found is not a critical error, continuing with update"
                    )
                    if update_last_indexed:
                        connector.last_indexed_at = datetime.now()
                        await session.commit()
                        logger.info(
                            f"Updated last_indexed_at to {connector.last_indexed_at} despite no issues found"
                        )
                    return 0, None
                else:
                    return 0, f"Failed to get Linear issues: {error}"

            logger.info(f"Retrieved {len(issues)} issues from Linear API")

        except Exception as e:
            logger.error(f"Exception when calling Linear API: {e!s}", exc_info=True)
            return 0, f"Failed to get Linear issues: {e!s}"

        if not issues:
            logger.info("No Linear issues found for the specified date range")
            if update_last_indexed:
                connector.last_indexed_at = datetime.now()
                await session.commit()
                logger.info(
                    f"Updated last_indexed_at to {connector.last_indexed_at} despite no issues found"
                )
            return 0, None  # Return None instead of error message when no issues found

        # Log issue IDs and titles for debugging
        logger.info("Issues retrieved from Linear API:")
        for idx, issue in enumerate(issues[:10]):  # Log first 10 issues
            logger.info(
                f"  {idx + 1}. {issue.get('identifier', 'Unknown')} - {issue.get('title', 'Unknown')} - Created: {issue.get('createdAt', 'Unknown')} - Updated: {issue.get('updatedAt', 'Unknown')}"
            )
        if len(issues) > 10:
            logger.info(f"  ...and {len(issues) - 10} more issues")

        # Track the number of documents indexed
        documents_indexed = 0
        documents_skipped = 0
        skipped_issues = []

        await task_logger.log_task_progress(
            log_entry,
            f"Starting to process {len(issues)} Linear issues",
            {"stage": "process_issues", "total_issues": len(issues)},
        )

        # Process each issue
        for issue in issues:
            try:
                issue_id = issue.get("key")
                issue_identifier = issue.get("id", "")
                issue_title = issue.get("key", "")

                if not issue_id or not issue_title:
                    logger.warning(
                        f"Skipping issue with missing ID or title: {issue_id or 'Unknown'}"
                    )
                    skipped_issues.append(
                        f"{issue_identifier or 'Unknown'} (missing data)"
                    )
                    documents_skipped += 1
                    continue

                # Format the issue first to get well-structured data
                formatted_issue = linear_client.format_issue(issue)

                # Convert issue to markdown format
                issue_content = linear_client.format_issue_to_markdown(formatted_issue)

                if not issue_content:
                    logger.warning(
                        f"Skipping issue with no content: {issue_identifier} - {issue_title}"
                    )
                    skipped_issues.append(f"{issue_identifier} (no content)")
                    documents_skipped += 1
                    continue

                # Create a short summary for the embedding
                # This avoids using the LLM and just uses the issue data directly
                state = formatted_issue.get("state", "Unknown")
                description = formatted_issue.get("description", "")
                # Truncate description if it's too long for the summary
                if description and len(description) > 500:
                    description = description[:497] + "..."

                # Create a simple summary from the issue data
                summary_content = f"Linear Issue {issue_identifier}: {issue_title}\n\nStatus: {state}\n\n"
                if description:
                    summary_content += f"Description: {description}\n\n"

                # Add comment count
                comment_count = len(formatted_issue.get("comments", []))
                summary_content += f"Comments: {comment_count}"

                content_hash = generate_content_hash(issue_content, search_space_id)

                # Check if document with this content hash already exists
                existing_doc_by_hash_result = await session.execute(
                    select(Document).where(Document.content_hash == content_hash)
                )
                existing_document_by_hash = (
                    existing_doc_by_hash_result.scalars().first()
                )

                if existing_document_by_hash:
                    logger.info(
                        f"Document with content hash {content_hash} already exists for issue {issue_identifier}. Skipping processing."
                    )
                    documents_skipped += 1
                    continue

                # Generate embedding for the summary
                summary_embedding = config.embedding_model_instance.embed(
                    summary_content
                )

                # Process chunks - using the full issue content with comments
                chunks = [
                    Chunk(
                        content=chunk.text,
                        embedding=config.embedding_model_instance.embed(chunk.text),
                    )
                    for chunk in config.chunker_instance.chunk(issue_content)
                ]

                # Create and store new document
                logger.info(
                    f"Creating new document for issue {issue_identifier} - {issue_title}"
                )
                document = Document(
                    search_space_id=search_space_id,
                    title=f"Linear - {issue_identifier}: {issue_title}",
                    document_type=DocumentType.LINEAR_CONNECTOR,
                    document_metadata={
                        "issue_id": issue_id,
                        "issue_identifier": issue_identifier,
                        "issue_title": issue_title,
                        "state": state,
                        "comment_count": comment_count,
                        "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    },
                    content=summary_content,
                    content_hash=content_hash,
                    embedding=summary_embedding,
                    chunks=chunks,
                )

                session.add(document)
                documents_indexed += 1
                logger.info(
                    f"Successfully indexed new issue {issue_identifier} - {issue_title}"
                )

            except Exception as e:
                logger.error(
                    f"Error processing issue {issue.get('identifier', 'Unknown')}: {e!s}",
                    exc_info=True,
                )
                skipped_issues.append(
                    f"{issue.get('identifier', 'Unknown')} (processing error)"
                )
                documents_skipped += 1
                continue  # Skip this issue and continue with others

        # Update the last_indexed_at timestamp for the connector only if requested
        total_processed = documents_indexed
        if update_last_indexed:
            connector.last_indexed_at = datetime.now()
            logger.info(f"Updated last_indexed_at to {connector.last_indexed_at}")

        # Commit all changes
        await session.commit()
        logger.info("Successfully committed all Linear document changes to database")

        # Log success
        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed Linear indexing for connector {connector_id}",
            {
                "issues_processed": total_processed,
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
                "skipped_issues_count": len(skipped_issues),
            },
        )

        logger.info(
            f"Linear indexing completed: {documents_indexed} new issues, {documents_skipped} skipped"
        )
        return (
            total_processed,
            None,
        )  # Return None as the error message to indicate success

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during Linear indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(f"Database error: {db_error!s}", exc_info=True)
        return 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index Linear issues for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index Linear issues: {e!s}", exc_info=True)
        return 0, f"Failed to index Linear issues: {e!s}"


async def index_discord_messages(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    update_last_indexed: bool = True,
) -> tuple[int, str | None]:
    """
    Index Discord messages from all accessible channels.

    Args:
        session: Database session
        connector_id: ID of the Discord connector
        search_space_id: ID of the search space to store documents in
        update_last_indexed: Whether to update the last_indexed_at timestamp (default: True)

    Returns:
        Tuple containing (number of documents indexed, error message or None)
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="discord_messages_indexing",
        source="connector_indexing_task",
        message=f"Starting Discord messages indexing for connector {connector_id}",
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
            f"Retrieving Discord connector {connector_id} from database",
            {"stage": "connector_retrieval"},
        )

        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.DISCORD_CONNECTOR,
            )
        )
        connector = result.scalars().first()

        if not connector:
            await task_logger.log_task_failure(
                log_entry,
                f"Connector with ID {connector_id} not found or is not a Discord connector",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return (
                0,
                f"Connector with ID {connector_id} not found or is not a Discord connector",
            )

        # Get the Discord token from the connector config
        discord_token = connector.config.get("DISCORD_BOT_TOKEN")
        if not discord_token:
            await task_logger.log_task_failure(
                log_entry,
                f"Discord token not found in connector config for connector {connector_id}",
                "Missing Discord token",
                {"error_type": "MissingToken"},
            )
            return 0, "Discord token not found in connector config"

        logger.info(f"Starting Discord indexing for connector {connector_id}")

        # Initialize Discord client
        await task_logger.log_task_progress(
            log_entry,
            f"Initializing Discord client for connector {connector_id}",
            {"stage": "client_initialization"},
        )

        discord_client = DiscordConnector(token=discord_token)

        # Calculate date range
        if start_date is None or end_date is None:
            # Fall back to calculating dates based on last_indexed_at
            calculated_end_date = datetime.now(UTC)

            # Use last_indexed_at as start date if available, otherwise use 365 days ago
            if connector.last_indexed_at:
                calculated_start_date = connector.last_indexed_at.replace(tzinfo=UTC)
                logger.info(
                    f"Using last_indexed_at ({calculated_start_date.strftime('%Y-%m-%d')}) as start date"
                )
            else:
                calculated_start_date = calculated_end_date - timedelta(days=365)
                logger.info(
                    f"No last_indexed_at found, using {calculated_start_date.strftime('%Y-%m-%d')} (365 days ago) as start date"
                )

            # Use calculated dates if not provided, convert to ISO format for Discord API
            if start_date is None:
                start_date_iso = calculated_start_date.isoformat()
            else:
                # Convert YYYY-MM-DD to ISO format
                start_date_iso = (
                    datetime.strptime(start_date, "%Y-%m-%d")
                    .replace(tzinfo=UTC)
                    .isoformat()
                )

            if end_date is None:
                end_date_iso = calculated_end_date.isoformat()
            else:
                # Convert YYYY-MM-DD to ISO format
                end_date_iso = (
                    datetime.strptime(end_date, "%Y-%m-%d")
                    .replace(tzinfo=UTC)
                    .isoformat()
                )
        else:
            # Convert provided dates to ISO format for Discord API
            start_date_iso = (
                datetime.strptime(start_date, "%Y-%m-%d")
                .replace(tzinfo=UTC)
                .isoformat()
            )
            end_date_iso = (
                datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=UTC).isoformat()
            )

        logger.info(
            f"Indexing Discord messages from {start_date_iso} to {end_date_iso}"
        )

        documents_indexed = 0
        documents_skipped = 0
        skipped_channels = []

        try:
            await task_logger.log_task_progress(
                log_entry,
                f"Starting Discord bot and fetching guilds for connector {connector_id}",
                {"stage": "fetch_guilds"},
            )

            logger.info("Starting Discord bot to fetch guilds")
            discord_client._bot_task = asyncio.create_task(discord_client.start_bot())
            await discord_client._wait_until_ready()

            logger.info("Fetching Discord guilds")
            guilds = await discord_client.get_guilds()
            logger.info(f"Found {len(guilds)} guilds")
        except Exception as e:
            await task_logger.log_task_failure(
                log_entry,
                f"Failed to get Discord guilds for connector {connector_id}",
                str(e),
                {"error_type": "GuildFetchError"},
            )
            logger.error(f"Failed to get Discord guilds: {e!s}", exc_info=True)
            await discord_client.close_bot()
            return 0, f"Failed to get Discord guilds: {e!s}"
        if not guilds:
            await task_logger.log_task_success(
                log_entry,
                f"No Discord guilds found for connector {connector_id}",
                {"guilds_found": 0},
            )
            logger.info("No Discord guilds found to index")
            await discord_client.close_bot()
            return 0, "No Discord guilds found"

        # Process each guild and channel
        await task_logger.log_task_progress(
            log_entry,
            f"Starting to process {len(guilds)} Discord guilds",
            {"stage": "process_guilds", "total_guilds": len(guilds)},
        )

        for guild in guilds:
            guild_id = guild["id"]
            guild_name = guild["name"]
            logger.info(f"Processing guild: {guild_name} ({guild_id})")
            try:
                channels = await discord_client.get_text_channels(guild_id)
                if not channels:
                    logger.info(f"No channels found in guild {guild_name}. Skipping.")
                    skipped_channels.append(f"{guild_name} (no channels)")
                    documents_skipped += 1
                    continue

                for channel in channels:
                    channel_id = channel["id"]
                    channel_name = channel["name"]

                    try:
                        messages = await discord_client.get_channel_history(
                            channel_id=channel_id,
                            start_date=start_date_iso,
                            end_date=end_date_iso,
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to get messages for channel {channel_name}: {e!s}"
                        )
                        skipped_channels.append(
                            f"{guild_name}#{channel_name} (fetch error)"
                        )
                        documents_skipped += 1
                        continue

                    if not messages:
                        logger.info(
                            f"No messages found in channel {channel_name} for the specified date range."
                        )
                        documents_skipped += 1
                        continue

                    # Format messages
                    formatted_messages = []
                    for msg in messages:
                        # Skip system messages if needed (Discord has some types)
                        if msg.get("type") in ["system"]:
                            continue
                        formatted_messages.append(msg)

                    if not formatted_messages:
                        logger.info(
                            f"No valid messages found in channel {channel_name} after filtering."
                        )
                        documents_skipped += 1
                        continue

                    # Convert messages to markdown format
                    channel_content = (
                        f"# Discord Channel: {guild_name} / {channel_name}\n\n"
                    )
                    for msg in formatted_messages:
                        user_name = msg.get("author_name", "Unknown User")
                        timestamp = msg.get("created_at", "Unknown Time")
                        text = msg.get("content", "")
                        channel_content += (
                            f"## {user_name} ({timestamp})\n\n{text}\n\n---\n\n"
                        )

                    # Format document metadata
                    metadata_sections = [
                        (
                            "METADATA",
                            [
                                f"GUILD_NAME: {guild_name}",
                                f"GUILD_ID: {guild_id}",
                                f"CHANNEL_NAME: {channel_name}",
                                f"CHANNEL_ID: {channel_id}",
                                f"MESSAGE_COUNT: {len(formatted_messages)}",
                            ],
                        ),
                        (
                            "CONTENT",
                            [
                                "FORMAT: markdown",
                                "TEXT_START",
                                channel_content,
                                "TEXT_END",
                            ],
                        ),
                    ]

                    # Build the document string
                    document_parts = []
                    document_parts.append("<DOCUMENT>")
                    for section_title, section_content in metadata_sections:
                        document_parts.append(f"<{section_title}>")
                        document_parts.extend(section_content)
                        document_parts.append(f"</{section_title}>")
                    document_parts.append("</DOCUMENT>")
                    combined_document_string = "\n".join(document_parts)
                    content_hash = generate_content_hash(
                        combined_document_string, search_space_id
                    )

                    # Check if document with this content hash already exists
                    existing_doc_by_hash_result = await session.execute(
                        select(Document).where(Document.content_hash == content_hash)
                    )
                    existing_document_by_hash = (
                        existing_doc_by_hash_result.scalars().first()
                    )

                    if existing_document_by_hash:
                        logger.info(
                            f"Document with content hash {content_hash} already exists for channel {guild_name}#{channel_name}. Skipping processing."
                        )
                        documents_skipped += 1
                        continue

                    # Get user's long context LLM
                    user_llm = await get_user_long_context_llm(session, user_id)
                    if not user_llm:
                        logger.error(
                            f"No long context LLM configured for user {user_id}"
                        )
                        skipped_channels.append(
                            f"{guild_name}#{channel_name} (no LLM configured)"
                        )
                        documents_skipped += 1
                        continue

                    # Generate summary using summary_chain
                    summary_chain = SUMMARY_PROMPT_TEMPLATE | user_llm
                    summary_result = await summary_chain.ainvoke(
                        {"document": combined_document_string}
                    )
                    summary_content = summary_result.content
                    summary_embedding = await asyncio.to_thread(
                        config.embedding_model_instance.embed, summary_content
                    )

                    # Process chunks
                    raw_chunks = await asyncio.to_thread(
                        config.chunker_instance.chunk, channel_content
                    )

                    chunk_texts = [
                        chunk.text for chunk in raw_chunks if chunk.text.strip()
                    ]
                    chunk_embeddings = await asyncio.to_thread(
                        lambda texts: [
                            config.embedding_model_instance.embed(t) for t in texts
                        ],
                        chunk_texts,
                    )

                    chunks = [
                        Chunk(content=raw_chunk.text, embedding=embedding)
                        for raw_chunk, embedding in zip(
                            raw_chunks, chunk_embeddings, strict=False
                        )
                    ]

                    # Create and store new document
                    document = Document(
                        search_space_id=search_space_id,
                        title=f"Discord - {guild_name}#{channel_name}",
                        document_type=DocumentType.DISCORD_CONNECTOR,
                        document_metadata={
                            "guild_name": guild_name,
                            "guild_id": guild_id,
                            "channel_name": channel_name,
                            "channel_id": channel_id,
                            "message_count": len(formatted_messages),
                            "start_date": start_date_iso,
                            "end_date": end_date_iso,
                            "indexed_at": datetime.now(UTC).strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                        },
                        content=summary_content,
                        content_hash=content_hash,
                        embedding=summary_embedding,
                        chunks=chunks,
                    )

                    session.add(document)
                    documents_indexed += 1
                    logger.info(
                        f"Successfully indexed new channel {guild_name}#{channel_name} with {len(formatted_messages)} messages"
                    )

            except Exception as e:
                logger.error(
                    f"Error processing guild {guild_name}: {e!s}", exc_info=True
                )
                skipped_channels.append(f"{guild_name} (processing error)")
                documents_skipped += 1
                continue

        if update_last_indexed and documents_indexed > 0:
            connector.last_indexed_at = datetime.now(UTC)
            logger.info(f"Updated last_indexed_at to {connector.last_indexed_at}")

        await session.commit()
        await discord_client.close_bot()

        # Prepare result message
        result_message = None
        if skipped_channels:
            result_message = f"Processed {documents_indexed} channels. Skipped {len(skipped_channels)} channels: {', '.join(skipped_channels)}"
        else:
            result_message = f"Processed {documents_indexed} channels."

        # Log success
        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed Discord indexing for connector {connector_id}",
            {
                "channels_processed": documents_indexed,
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
                "skipped_channels_count": len(skipped_channels),
                "guilds_processed": len(guilds),
                "result_message": result_message,
            },
        )

        logger.info(
            f"Discord indexing completed: {documents_indexed} new channels, {documents_skipped} skipped"
        )
        return documents_indexed, result_message

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during Discord indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(
            f"Database error during Discord indexing: {db_error!s}", exc_info=True
        )
        return 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index Discord messages for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index Discord messages: {e!s}", exc_info=True)
        return 0, f"Failed to index Discord messages: {e!s}"


async def index_jira_issues(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    update_last_indexed: bool = True,
) -> tuple[int, str | None]:
    """
    Index Jira issues and comments.

    Args:
        session: Database session
        connector_id: ID of the Jira connector
        search_space_id: ID of the search space to store documents in
        user_id: User ID
        start_date: Start date for indexing (YYYY-MM-DD format)
        end_date: End date for indexing (YYYY-MM-DD format)
        update_last_indexed: Whether to update the last_indexed_at timestamp (default: True)

    Returns:
        Tuple containing (number of documents indexed, error message or None)
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="jira_issues_indexing",
        source="connector_indexing_task",
        message=f"Starting Jira issues indexing for connector {connector_id}",
        metadata={
            "connector_id": connector_id,
            "user_id": str(user_id),
            "start_date": start_date,
            "end_date": end_date,
        },
    )

    try:
        # Get the connector from the database
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.JIRA_CONNECTOR,
            )
        )
        connector = result.scalars().first()

        if not connector:
            await task_logger.log_task_failure(
                log_entry,
                f"Connector with ID {connector_id} not found",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return 0, f"Connector with ID {connector_id} not found"

        # Get the Jira credentials from the connector config
        jira_email = connector.config.get("JIRA_EMAIL")
        jira_api_token = connector.config.get("JIRA_API_TOKEN")
        jira_base_url = connector.config.get("JIRA_BASE_URL")

        if not jira_email or not jira_api_token or not jira_base_url:
            await task_logger.log_task_failure(
                log_entry,
                f"Jira credentials not found in connector config for connector {connector_id}",
                "Missing Jira credentials",
                {"error_type": "MissingCredentials"},
            )
            return 0, "Jira credentials not found in connector config"

        # Initialize Jira client
        await task_logger.log_task_progress(
            log_entry,
            f"Initializing Jira client for connector {connector_id}",
            {"stage": "client_initialization"},
        )

        jira_client = JiraConnector(
            base_url=jira_base_url, email=jira_email, api_token=jira_api_token
        )

        # Calculate date range
        if start_date is None or end_date is None:
            # Fall back to calculating dates based on last_indexed_at
            calculated_end_date = datetime.now()

            # Use last_indexed_at as start date if available, otherwise use 365 days ago
            if connector.last_indexed_at:
                # Convert dates to be comparable (both timezone-naive)
                last_indexed_naive = (
                    connector.last_indexed_at.replace(tzinfo=None)
                    if connector.last_indexed_at.tzinfo
                    else connector.last_indexed_at
                )

                # Check if last_indexed_at is in the future or after end_date
                if last_indexed_naive > calculated_end_date:
                    logger.warning(
                        f"Last indexed date ({last_indexed_naive.strftime('%Y-%m-%d')}) is in the future. Using 365 days ago instead."
                    )
                    calculated_start_date = calculated_end_date - timedelta(days=365)
                else:
                    calculated_start_date = last_indexed_naive
                    logger.info(
                        f"Using last_indexed_at ({calculated_start_date.strftime('%Y-%m-%d')}) as start date"
                    )
            else:
                calculated_start_date = calculated_end_date - timedelta(
                    days=365
                )  # Use 365 days as default
                logger.info(
                    f"No last_indexed_at found, using {calculated_start_date.strftime('%Y-%m-%d')} (365 days ago) as start date"
                )

            # Use calculated dates if not provided
            start_date_str = (
                start_date if start_date else calculated_start_date.strftime("%Y-%m-%d")
            )
            end_date_str = (
                end_date if end_date else calculated_end_date.strftime("%Y-%m-%d")
            )
        else:
            # Use provided dates
            start_date_str = start_date
            end_date_str = end_date

        await task_logger.log_task_progress(
            log_entry,
            f"Fetching Jira issues from {start_date_str} to {end_date_str}",
            {
                "stage": "fetching_issues",
                "start_date": start_date_str,
                "end_date": end_date_str,
            },
        )

        # Get issues within date range
        try:
            issues, error = jira_client.get_issues_by_date_range(
                start_date=start_date_str, end_date=end_date_str, include_comments=True
            )

            if error:
                logger.error(f"Failed to get Jira issues: {error}")

                # Don't treat "No issues found" as an error that should stop indexing
                if "No issues found" in error:
                    logger.info(
                        "No issues found is not a critical error, continuing with update"
                    )
                    if update_last_indexed:
                        connector.last_indexed_at = datetime.now()
                        await session.commit()
                        logger.info(
                            f"Updated last_indexed_at to {connector.last_indexed_at} despite no issues found"
                        )

                    await task_logger.log_task_success(
                        log_entry,
                        f"No Jira issues found in date range {start_date_str} to {end_date_str}",
                        {"issues_found": 0},
                    )
                    return 0, None
                else:
                    await task_logger.log_task_failure(
                        log_entry,
                        f"Failed to get Jira issues: {error}",
                        "API Error",
                        {"error_type": "APIError"},
                    )
                    return 0, f"Failed to get Jira issues: {error}"

            logger.info(f"Retrieved {len(issues)} issues from Jira API")

        except Exception as e:
            logger.error(f"Error fetching Jira issues: {e!s}", exc_info=True)
            return 0, f"Error fetching Jira issues: {e!s}"

        # Process and index each issue
        documents_indexed = 0
        skipped_issues = []
        documents_skipped = 0

        for issue in issues:
            try:
                issue_id = issue.get("key")
                issue_identifier = issue.get("key", "")
                issue_title = issue.get("id", "")

                if not issue_id or not issue_title:
                    logger.warning(
                        f"Skipping issue with missing ID or title: {issue_id or 'Unknown'}"
                    )
                    skipped_issues.append(
                        f"{issue_identifier or 'Unknown'} (missing data)"
                    )
                    documents_skipped += 1
                    continue

                # Format the issue for better readability
                formatted_issue = jira_client.format_issue(issue)

                # Convert to markdown
                issue_content = jira_client.format_issue_to_markdown(formatted_issue)

                if not issue_content:
                    logger.warning(
                        f"Skipping issue with no content: {issue_identifier} - {issue_title}"
                    )
                    skipped_issues.append(f"{issue_identifier} (no content)")
                    documents_skipped += 1
                    continue

                # Create a simple summary
                summary_content = f"Jira Issue {issue_identifier}: {issue_title}\n\nStatus: {formatted_issue.get('status', 'Unknown')}\n\n"
                if formatted_issue.get("description"):
                    summary_content += (
                        f"Description: {formatted_issue.get('description')}\n\n"
                    )

                # Add comment count
                comment_count = len(formatted_issue.get("comments", []))
                summary_content += f"Comments: {comment_count}"

                # Generate content hash
                content_hash = generate_content_hash(issue_content, search_space_id)

                # Check if document already exists
                existing_doc_by_hash_result = await session.execute(
                    select(Document).where(Document.content_hash == content_hash)
                )
                existing_document_by_hash = (
                    existing_doc_by_hash_result.scalars().first()
                )

                if existing_document_by_hash:
                    logger.info(
                        f"Document with content hash {content_hash} already exists for issue {issue_identifier}. Skipping processing."
                    )
                    documents_skipped += 1
                    continue

                # Generate embedding for the summary
                summary_embedding = config.embedding_model_instance.embed(
                    summary_content
                )

                # Process chunks - using the full issue content with comments
                chunks = [
                    Chunk(
                        content=chunk.text,
                        embedding=config.embedding_model_instance.embed(chunk.text),
                    )
                    for chunk in config.chunker_instance.chunk(issue_content)
                ]

                # Create and store new document
                logger.info(
                    f"Creating new document for issue {issue_identifier} - {issue_title}"
                )
                document = Document(
                    search_space_id=search_space_id,
                    title=f"Jira - {issue_identifier}: {issue_title}",
                    document_type=DocumentType.JIRA_CONNECTOR,
                    document_metadata={
                        "issue_id": issue_id,
                        "issue_identifier": issue_identifier,
                        "issue_title": issue_title,
                        "state": formatted_issue.get("status", "Unknown"),
                        "comment_count": comment_count,
                        "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    },
                    content=summary_content,
                    content_hash=content_hash,
                    embedding=summary_embedding,
                    chunks=chunks,
                )

                session.add(document)
                documents_indexed += 1
                logger.info(
                    f"Successfully indexed new issue {issue_identifier} - {issue_title}"
                )

            except Exception as e:
                logger.error(
                    f"Error processing issue {issue.get('identifier', 'Unknown')}: {e!s}",
                    exc_info=True,
                )
                skipped_issues.append(
                    f"{issue.get('identifier', 'Unknown')} (processing error)"
                )
                documents_skipped += 1
                continue  # Skip this issue and continue with others

        # Update the last_indexed_at timestamp for the connector only if requested
        total_processed = documents_indexed
        if update_last_indexed:
            connector.last_indexed_at = datetime.now()
            logger.info(f"Updated last_indexed_at to {connector.last_indexed_at}")

        # Commit all changes
        await session.commit()
        logger.info("Successfully committed all JIRA document changes to database")

        # Log success
        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed JIRA indexing for connector {connector_id}",
            {
                "issues_processed": total_processed,
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
                "skipped_issues_count": len(skipped_issues),
            },
        )

        logger.info(
            f"JIRA indexing completed: {documents_indexed} new issues, {documents_skipped} skipped"
        )
        return (
            total_processed,
            None,
        )  # Return None as the error message to indicate success

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during JIRA indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(f"Database error: {db_error!s}", exc_info=True)
        return 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index JIRA issues for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index JIRA issues: {e!s}", exc_info=True)
        return 0, f"Failed to index JIRA issues: {e!s}"


async def index_confluence_pages(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    update_last_indexed: bool = True,
) -> tuple[int, str | None]:
    """
    Index Confluence pages and comments.

    Args:
        session: Database session
        connector_id: ID of the Confluence connector
        search_space_id: ID of the search space to store documents in
        user_id: User ID
        start_date: Start date for indexing (YYYY-MM-DD format)
        end_date: End date for indexing (YYYY-MM-DD format)
        update_last_indexed: Whether to update the last_indexed_at timestamp (default: True)

    Returns:
        Tuple containing (number of documents indexed, error message or None)
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="confluence_pages_indexing",
        source="connector_indexing_task",
        message=f"Starting Confluence pages indexing for connector {connector_id}",
        metadata={
            "connector_id": connector_id,
            "user_id": str(user_id),
            "start_date": start_date,
            "end_date": end_date,
        },
    )

    try:
        # Get the connector from the database
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.CONFLUENCE_CONNECTOR,
            )
        )
        connector = result.scalars().first()

        if not connector:
            await task_logger.log_task_failure(
                log_entry,
                f"Connector with ID {connector_id} not found",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return 0, f"Connector with ID {connector_id} not found"

        # Get the Confluence credentials from the connector config
        confluence_email = connector.config.get("CONFLUENCE_EMAIL")
        confluence_api_token = connector.config.get("CONFLUENCE_API_TOKEN")
        confluence_base_url = connector.config.get("CONFLUENCE_BASE_URL")

        if not confluence_email or not confluence_api_token or not confluence_base_url:
            await task_logger.log_task_failure(
                log_entry,
                f"Confluence credentials not found in connector config for connector {connector_id}",
                "Missing Confluence credentials",
                {"error_type": "MissingCredentials"},
            )
            return 0, "Confluence credentials not found in connector config"

        # Initialize Confluence client
        await task_logger.log_task_progress(
            log_entry,
            f"Initializing Confluence client for connector {connector_id}",
            {"stage": "client_initialization"},
        )

        confluence_client = ConfluenceConnector(
            base_url=confluence_base_url,
            email=confluence_email,
            api_token=confluence_api_token,
        )

        # Calculate date range
        if start_date is None or end_date is None:
            # Fall back to calculating dates based on last_indexed_at
            calculated_end_date = datetime.now()

            # Use last_indexed_at as start date if available, otherwise use 365 days ago
            if connector.last_indexed_at:
                # Convert dates to be comparable (both timezone-naive)
                last_indexed_naive = (
                    connector.last_indexed_at.replace(tzinfo=None)
                    if connector.last_indexed_at.tzinfo
                    else connector.last_indexed_at
                )

                # Check if last_indexed_at is in the future or after end_date
                if last_indexed_naive > calculated_end_date:
                    logger.warning(
                        f"Last indexed date ({last_indexed_naive.strftime('%Y-%m-%d')}) is in the future. Using 365 days ago instead."
                    )
                    calculated_start_date = calculated_end_date - timedelta(days=365)
                else:
                    calculated_start_date = last_indexed_naive
                    logger.info(
                        f"Using last_indexed_at ({calculated_start_date.strftime('%Y-%m-%d')}) as start date"
                    )
            else:
                calculated_start_date = calculated_end_date - timedelta(
                    days=365
                )  # Use 365 days as default
                logger.info(
                    f"No last_indexed_at found, using {calculated_start_date.strftime('%Y-%m-%d')} (365 days ago) as start date"
                )

            # Use calculated dates if not provided
            start_date_str = (
                start_date if start_date else calculated_start_date.strftime("%Y-%m-%d")
            )
            end_date_str = (
                end_date if end_date else calculated_end_date.strftime("%Y-%m-%d")
            )
        else:
            # Use provided dates
            start_date_str = start_date
            end_date_str = end_date

        await task_logger.log_task_progress(
            log_entry,
            f"Fetching Confluence pages from {start_date_str} to {end_date_str}",
            {
                "stage": "fetching_pages",
                "start_date": start_date_str,
                "end_date": end_date_str,
            },
        )

        # Get pages within date range
        try:
            pages, error = confluence_client.get_pages_by_date_range(
                start_date=start_date_str, end_date=end_date_str, include_comments=True
            )

            if error:
                logger.error(f"Failed to get Confluence pages: {error}")

                # Don't treat "No pages found" as an error that should stop indexing
                if "No pages found" in error:
                    logger.info(
                        "No pages found is not a critical error, continuing with update"
                    )
                    if update_last_indexed:
                        connector.last_indexed_at = datetime.now()
                        await session.commit()
                        logger.info(
                            f"Updated last_indexed_at to {connector.last_indexed_at} despite no pages found"
                        )

                    await task_logger.log_task_success(
                        log_entry,
                        f"No Confluence pages found in date range {start_date_str} to {end_date_str}",
                        {"pages_found": 0},
                    )
                    return 0, None
                else:
                    await task_logger.log_task_failure(
                        log_entry,
                        f"Failed to get Confluence pages: {error}",
                        "API Error",
                        {"error_type": "APIError"},
                    )
                    return 0, f"Failed to get Confluence pages: {error}"

            logger.info(f"Retrieved {len(pages)} pages from Confluence API")

        except Exception as e:
            logger.error(f"Error fetching Confluence pages: {e!s}", exc_info=True)
            return 0, f"Error fetching Confluence pages: {e!s}"

        # Process and index each page
        documents_indexed = 0
        skipped_pages = []
        documents_skipped = 0

        for page in pages:
            try:
                page_id = page.get("id")
                page_title = page.get("title", "")
                space_id = page.get("spaceId", "")

                if not page_id or not page_title:
                    logger.warning(
                        f"Skipping page with missing ID or title: {page_id or 'Unknown'}"
                    )
                    skipped_pages.append(f"{page_title or 'Unknown'} (missing data)")
                    documents_skipped += 1
                    continue

                # Extract page content
                page_content = ""
                if page.get("body") and page["body"].get("storage"):
                    page_content = page["body"]["storage"].get("value", "")

                # Add comments to content
                comments = page.get("comments", [])
                comments_content = ""
                if comments:
                    comments_content = "\n\n## Comments\n\n"
                    for comment in comments:
                        comment_body = ""
                        if comment.get("body") and comment["body"].get("storage"):
                            comment_body = comment["body"]["storage"].get("value", "")

                        comment_author = comment.get("version", {}).get(
                            "authorId", "Unknown"
                        )
                        comment_date = comment.get("version", {}).get("createdAt", "")

                        comments_content += f"**Comment by {comment_author}** ({comment_date}):\n{comment_body}\n\n"

                # Combine page content with comments
                full_content = f"# {page_title}\n\n{page_content}{comments_content}"

                if not full_content.strip():
                    logger.warning(f"Skipping page with no content: {page_title}")
                    skipped_pages.append(f"{page_title} (no content)")
                    documents_skipped += 1
                    continue

                # Create a simple summary
                summary_content = (
                    f"Confluence Page: {page_title}\n\nSpace ID: {space_id}\n\n"
                )
                if page_content:
                    # Take first 500 characters of content for summary
                    content_preview = page_content[:500]
                    if len(page_content) > 500:
                        content_preview += "..."
                    summary_content += f"Content Preview: {content_preview}\n\n"

                # Add comment count
                comment_count = len(comments)
                summary_content += f"Comments: {comment_count}"

                # Generate content hash
                content_hash = generate_content_hash(full_content, search_space_id)

                # Check if document already exists
                existing_doc_by_hash_result = await session.execute(
                    select(Document).where(Document.content_hash == content_hash)
                )
                existing_document_by_hash = (
                    existing_doc_by_hash_result.scalars().first()
                )

                if existing_document_by_hash:
                    logger.info(
                        f"Document with content hash {content_hash} already exists for page {page_title}. Skipping processing."
                    )
                    documents_skipped += 1
                    continue

                # Generate embedding for the summary
                summary_embedding = config.embedding_model_instance.embed(
                    summary_content
                )

                # Process chunks - using the full page content with comments
                chunks = [
                    Chunk(
                        content=chunk.text,
                        embedding=config.embedding_model_instance.embed(chunk.text),
                    )
                    for chunk in config.chunker_instance.chunk(full_content)
                ]

                # Create and store new document
                logger.info(f"Creating new document for page {page_title}")
                document = Document(
                    search_space_id=search_space_id,
                    title=f"Confluence - {page_title}",
                    document_type=DocumentType.CONFLUENCE_CONNECTOR,
                    document_metadata={
                        "page_id": page_id,
                        "page_title": page_title,
                        "space_id": space_id,
                        "comment_count": comment_count,
                        "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    },
                    content=summary_content,
                    content_hash=content_hash,
                    embedding=summary_embedding,
                    chunks=chunks,
                )

                session.add(document)
                documents_indexed += 1
                logger.info(f"Successfully indexed new page {page_title}")

            except Exception as e:
                logger.error(
                    f"Error processing page {page.get('title', 'Unknown')}: {e!s}",
                    exc_info=True,
                )
                skipped_pages.append(
                    f"{page.get('title', 'Unknown')} (processing error)"
                )
                documents_skipped += 1
                continue  # Skip this page and continue with others

        # Update the last_indexed_at timestamp for the connector only if requested
        total_processed = documents_indexed
        if update_last_indexed:
            connector.last_indexed_at = datetime.now()
            logger.info(f"Updated last_indexed_at to {connector.last_indexed_at}")

        # Commit all changes
        await session.commit()
        logger.info(
            "Successfully committed all Confluence document changes to database"
        )

        # Log success
        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed Confluence indexing for connector {connector_id}",
            {
                "pages_processed": total_processed,
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
                "skipped_pages_count": len(skipped_pages),
            },
        )

        logger.info(
            f"Confluence indexing completed: {documents_indexed} new pages, {documents_skipped} skipped"
        )
        return (
            total_processed,
            None,
        )  # Return None as the error message to indicate success

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during Confluence indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(f"Database error: {db_error!s}", exc_info=True)
        return 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index Confluence pages for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index Confluence pages: {e!s}", exc_info=True)
        return 0, f"Failed to index Confluence pages: {e!s}"
