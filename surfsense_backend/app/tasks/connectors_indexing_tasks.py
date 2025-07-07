from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select
from datetime import datetime, timedelta, timezone
from app.db import Document, DocumentType, Chunk, SearchSourceConnector, SearchSourceConnectorType, SearchSpace
from app.config import config
from app.prompts import SUMMARY_PROMPT_TEMPLATE
from app.services.llm_service import get_user_long_context_llm
from app.connectors.slack_history import SlackHistory
from app.connectors.notion_history import NotionHistoryConnector
from app.connectors.github_connector import GitHubConnector
from app.connectors.linear_connector import LinearConnector
from app.connectors.discord_connector import DiscordConnector
from slack_sdk.errors import SlackApiError
import logging
import asyncio

from app.utils.document_converters import generate_content_hash

# Set up logging
logger = logging.getLogger(__name__)

async def index_slack_messages(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str = None,
    end_date: str = None,
    update_last_indexed: bool = True
) -> Tuple[int, Optional[str]]:
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
    try:
        # Get the connector
        result = await session.execute(
            select(SearchSourceConnector)
            .filter(
                SearchSourceConnector.id == connector_id,
                SearchSourceConnector.connector_type == SearchSourceConnectorType.SLACK_CONNECTOR
            )
        )
        connector = result.scalars().first()
        
        if not connector:
            return 0, f"Connector with ID {connector_id} not found or is not a Slack connector"
        
        # Get the Slack token from the connector config
        slack_token = connector.config.get("SLACK_BOT_TOKEN")
        if not slack_token:
            return 0, "Slack token not found in connector config"
        
        # Initialize Slack client
        slack_client = SlackHistory(token=slack_token)
        
        # Calculate date range
        if start_date is None or end_date is None:
            # Fall back to calculating dates based on last_indexed_at
            calculated_end_date = datetime.now()
            
            # Use last_indexed_at as start date if available, otherwise use 365 days ago
            if connector.last_indexed_at:
                # Convert dates to be comparable (both timezone-naive)
                last_indexed_naive = connector.last_indexed_at.replace(tzinfo=None) if connector.last_indexed_at.tzinfo else connector.last_indexed_at
                
                # Check if last_indexed_at is in the future or after end_date
                if last_indexed_naive > calculated_end_date:
                    logger.warning(f"Last indexed date ({last_indexed_naive.strftime('%Y-%m-%d')}) is in the future. Using 365 days ago instead.")
                    calculated_start_date = calculated_end_date - timedelta(days=365)
                else:
                    calculated_start_date = last_indexed_naive
                    logger.info(f"Using last_indexed_at ({calculated_start_date.strftime('%Y-%m-%d')}) as start date")
            else:
                calculated_start_date = calculated_end_date - timedelta(days=365)  # Use 365 days as default
                logger.info(f"No last_indexed_at found, using {calculated_start_date.strftime('%Y-%m-%d')} (365 days ago) as start date")
            
            # Use calculated dates if not provided
            start_date_str = start_date if start_date else calculated_start_date.strftime("%Y-%m-%d")
            end_date_str = end_date if end_date else calculated_end_date.strftime("%Y-%m-%d")
        else:
            # Use provided dates
            start_date_str = start_date
            end_date_str = end_date
            
        logger.info(f"Indexing Slack messages from {start_date_str} to {end_date_str}")
        
        # Get all channels
        try:
            channels = slack_client.get_all_channels()
        except Exception as e:
            return 0, f"Failed to get Slack channels: {str(e)}"
        
        if not channels:
            return 0, "No Slack channels found"
            
        # Track the number of documents indexed
        documents_indexed = 0
        documents_skipped = 0
        skipped_channels = []
        
        # Process each channel
        for channel_obj in channels: # Modified loop to iterate over list of channel objects
            channel_id = channel_obj["id"]
            channel_name = channel_obj["name"]
            is_private = channel_obj["is_private"]
            is_member = channel_obj["is_member"] # This might be False for public channels too

            try:
                # If it's a private channel and the bot is not a member, skip.
                # For public channels, if they are listed by conversations.list, the bot can typically read history.
                # The `not_in_channel` error in get_conversation_history will be the ultimate gatekeeper if history is inaccessible.
                if is_private and not is_member:
                    logger.warning(f"Bot is not a member of private channel {channel_name} ({channel_id}). Skipping.")
                    skipped_channels.append(f"{channel_name} (private, bot not a member)")
                    documents_skipped += 1
                    continue
                
                # Get messages for this channel
                # The get_history_by_date_range now uses get_conversation_history, 
                # which handles 'not_in_channel' by returning [] and logging.
                messages, error = slack_client.get_history_by_date_range(
                    channel_id=channel_id,
                    start_date=start_date_str,
                    end_date=end_date_str,
                    limit=1000  # Limit to 1000 messages per channel
                )
                
                if error:
                    logger.warning(f"Error getting messages from channel {channel_name}: {error}")
                    skipped_channels.append(f"{channel_name} (error: {error})")
                    documents_skipped += 1
                    continue  # Skip this channel if there's an error
                
                if not messages:
                    logger.info(f"No messages found in channel {channel_name} for the specified date range.")
                    documents_skipped += 1
                    continue  # Skip if no messages
                
                # Format messages with user info
                formatted_messages = []
                for msg in messages:
                    # Skip bot messages and system messages
                    if msg.get("subtype") in ["bot_message", "channel_join", "channel_leave"]:
                        continue
                    
                    formatted_msg = slack_client.format_message(msg, include_user_info=True)
                    formatted_messages.append(formatted_msg)
                
                if not formatted_messages:
                    logger.info(f"No valid messages found in channel {channel_name} after filtering.")
                    documents_skipped += 1
                    continue  # Skip if no valid messages after filtering
                
                # Convert messages to markdown format
                channel_content = f"# Slack Channel: {channel_name}\n\n"
                
                for msg in formatted_messages:
                    user_name = msg.get("user_name", "Unknown User")
                    timestamp = msg.get("datetime", "Unknown Time")
                    text = msg.get("text", "")
                    
                    channel_content += f"## {user_name} ({timestamp})\n\n{text}\n\n---\n\n"
                
                # Format document metadata
                metadata_sections = [
                    ("METADATA", [
                        f"CHANNEL_NAME: {channel_name}",
                        f"CHANNEL_ID: {channel_id}",
                        # f"START_DATE: {start_date_str}",
                        # f"END_DATE: {end_date_str}",
                        f"MESSAGE_COUNT: {len(formatted_messages)}"
                    ]),
                    ("CONTENT", [
                        "FORMAT: markdown",
                        "TEXT_START",
                        channel_content,
                        "TEXT_END"
                    ])
                ]
                
                # Build the document string
                document_parts = []
                document_parts.append("<DOCUMENT>")
                
                for section_title, section_content in metadata_sections:
                    document_parts.append(f"<{section_title}>")
                    document_parts.extend(section_content)
                    document_parts.append(f"</{section_title}>")
                
                document_parts.append("</DOCUMENT>")
                combined_document_string = '\n'.join(document_parts)
                content_hash = generate_content_hash(combined_document_string, search_space_id)

                # Check if document with this content hash already exists
                existing_doc_by_hash_result = await session.execute(
                    select(Document).where(Document.content_hash == content_hash)
                )
                existing_document_by_hash = existing_doc_by_hash_result.scalars().first()
                
                if existing_document_by_hash:
                    logger.info(f"Document with content hash {content_hash} already exists for channel {channel_name}. Skipping processing.")
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
                summary_result = await summary_chain.ainvoke({"document": combined_document_string})
                summary_content = summary_result.content
                summary_embedding = config.embedding_model_instance.embed(summary_content)
                
                # Process chunks
                chunks = [
                    Chunk(content=chunk.text, embedding=config.embedding_model_instance.embed(chunk.text))
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
                        "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    },
                    content=summary_content,
                    embedding=summary_embedding,
                    chunks=chunks,
                    content_hash=content_hash,
                )
                
                session.add(document)
                documents_indexed += 1
                logger.info(f"Successfully indexed new channel {channel_name} with {len(formatted_messages)} messages")
                
            except SlackApiError as slack_error:
                logger.error(f"Slack API error for channel {channel_name}: {str(slack_error)}")
                skipped_channels.append(f"{channel_name} (Slack API error)")
                documents_skipped += 1
                continue  # Skip this channel and continue with others
            except Exception as e:
                logger.error(f"Error processing channel {channel_name}: {str(e)}")
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
        
        logger.info(f"Slack indexing completed: {documents_indexed} new channels, {documents_skipped} skipped")
        return total_processed, result_message
    
    except SQLAlchemyError as db_error:
        await session.rollback()
        logger.error(f"Database error: {str(db_error)}")
        return 0, f"Database error: {str(db_error)}"
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to index Slack messages: {str(e)}")
        return 0, f"Failed to index Slack messages: {str(e)}"

async def index_notion_pages(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str = None,
    end_date: str = None,
    update_last_indexed: bool = True
) -> Tuple[int, Optional[str]]:
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
    try:
        # Get the connector
        result = await session.execute(
            select(SearchSourceConnector)
            .filter(
                SearchSourceConnector.id == connector_id,
                SearchSourceConnector.connector_type == SearchSourceConnectorType.NOTION_CONNECTOR
            )
        )
        connector = result.scalars().first()
        
        if not connector:
            return 0, f"Connector with ID {connector_id} not found or is not a Notion connector"
        
        # Get the Notion token from the connector config
        notion_token = connector.config.get("NOTION_INTEGRATION_TOKEN")
        if not notion_token:
            return 0, "Notion integration token not found in connector config"
        
        # Initialize Notion client
        logger.info(f"Initializing Notion client for connector {connector_id}")
        notion_client = NotionHistoryConnector(token=notion_token)
        
        # Calculate date range
        if start_date is None or end_date is None:
            # Fall back to calculating dates
            calculated_end_date = datetime.now()
            calculated_start_date = calculated_end_date - timedelta(days=365)  # Check for last 1 year of pages
            
            # Use calculated dates if not provided
            if start_date is None:
                start_date_iso = calculated_start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            else:
                # Convert YYYY-MM-DD to ISO format
                start_date_iso = datetime.strptime(start_date, "%Y-%m-%d").strftime("%Y-%m-%dT%H:%M:%SZ")
                
            if end_date is None:
                end_date_iso = calculated_end_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            else:
                # Convert YYYY-MM-DD to ISO format
                end_date_iso = datetime.strptime(end_date, "%Y-%m-%d").strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            # Convert provided dates to ISO format for Notion API
            start_date_iso = datetime.strptime(start_date, "%Y-%m-%d").strftime("%Y-%m-%dT%H:%M:%SZ")
            end_date_iso = datetime.strptime(end_date, "%Y-%m-%d").strftime("%Y-%m-%dT%H:%M:%SZ")
        
        logger.info(f"Fetching Notion pages from {start_date_iso} to {end_date_iso}")
        
        # Get all pages
        try:
            pages = notion_client.get_all_pages(start_date=start_date_iso, end_date=end_date_iso)
            logger.info(f"Found {len(pages)} Notion pages")
        except Exception as e:
            logger.error(f"Error fetching Notion pages: {str(e)}", exc_info=True)
            return 0, f"Failed to get Notion pages: {str(e)}"
        
        if not pages:
            logger.info("No Notion pages found to index")
            return 0, "No Notion pages found"
        
        # Track the number of documents indexed
        documents_indexed = 0
        documents_skipped = 0
        skipped_pages = []
        
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
                
                logger.debug(f"Converting {len(page_content)} blocks to markdown for page {page_title}")
                markdown_content += process_blocks(page_content)
                
                # Format document metadata
                metadata_sections = [
                    ("METADATA", [
                        f"PAGE_TITLE: {page_title}",
                        f"PAGE_ID: {page_id}"
                    ]),
                    ("CONTENT", [
                        "FORMAT: markdown",
                        "TEXT_START",
                        markdown_content,
                        "TEXT_END"
                    ])
                ]
                
                # Build the document string
                document_parts = []
                document_parts.append("<DOCUMENT>")
                
                for section_title, section_content in metadata_sections:
                    document_parts.append(f"<{section_title}>")
                    document_parts.extend(section_content)
                    document_parts.append(f"</{section_title}>")
                
                document_parts.append("</DOCUMENT>")
                combined_document_string = '\n'.join(document_parts)
                content_hash = generate_content_hash(combined_document_string, search_space_id)

                # Check if document with this content hash already exists
                existing_doc_by_hash_result = await session.execute(
                    select(Document).where(Document.content_hash == content_hash)
                )
                existing_document_by_hash = existing_doc_by_hash_result.scalars().first()
                
                if existing_document_by_hash:
                    logger.info(f"Document with content hash {content_hash} already exists for page {page_title}. Skipping processing.")
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
                summary_result = await summary_chain.ainvoke({"document": combined_document_string})
                summary_content = summary_result.content
                summary_embedding = config.embedding_model_instance.embed(summary_content)
                
                # Process chunks
                logger.debug(f"Chunking content for page {page_title}")
                chunks = [
                    Chunk(content=chunk.text, embedding=config.embedding_model_instance.embed(chunk.text))
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
                        "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    },
                    content=summary_content,
                    content_hash=content_hash,
                    embedding=summary_embedding,
                    chunks=chunks
                )
                
                session.add(document)
                documents_indexed += 1
                logger.info(f"Successfully indexed new Notion page: {page_title}")
                
            except Exception as e:
                logger.error(f"Error processing Notion page {page.get('title', 'Unknown')}: {str(e)}", exc_info=True)
                skipped_pages.append(f"{page.get('title', 'Unknown')} (processing error)")
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
        
        logger.info(f"Notion indexing completed: {documents_indexed} new pages, {documents_skipped} skipped")
        return total_processed, result_message
    
    except SQLAlchemyError as db_error:
        await session.rollback()
        logger.error(f"Database error during Notion indexing: {str(db_error)}", exc_info=True)
        return 0, f"Database error: {str(db_error)}"
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to index Notion pages: {str(e)}", exc_info=True)
        return 0, f"Failed to index Notion pages: {str(e)}"

async def index_github_repos(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str = None,
    end_date: str = None,
    update_last_indexed: bool = True
) -> Tuple[int, Optional[str]]:
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
    documents_processed = 0
    errors = []

    try:
        # 1. Get the GitHub connector from the database
        result = await session.execute(
            select(SearchSourceConnector)
            .filter(
                SearchSourceConnector.id == connector_id,
                SearchSourceConnector.connector_type == SearchSourceConnectorType.GITHUB_CONNECTOR
            )
        )
        connector = result.scalars().first()

        if not connector:
            return 0, f"Connector with ID {connector_id} not found or is not a GitHub connector"

        # 2. Get the GitHub PAT and selected repositories from the connector config
        github_pat = connector.config.get("GITHUB_PAT")
        repo_full_names_to_index = connector.config.get("repo_full_names")

        if not github_pat:
            return 0, "GitHub Personal Access Token (PAT) not found in connector config"
        
        if not repo_full_names_to_index or not isinstance(repo_full_names_to_index, list):
             return 0, "'repo_full_names' not found or is not a list in connector config"

        # 3. Initialize GitHub connector client
        try:
            github_client = GitHubConnector(token=github_pat)
        except ValueError as e:
            return 0, f"Failed to initialize GitHub client: {str(e)}"

        # 4. Validate selected repositories
        #    For simplicity, we'll proceed with the list provided.
        #    If a repo is inaccessible, get_repository_files will likely fail gracefully later.
        logger.info(f"Starting indexing for {len(repo_full_names_to_index)} selected repositories.")
        if start_date and end_date:
            logger.info(f"Date range requested: {start_date} to {end_date} (Note: GitHub indexing processes all files regardless of dates)")

        # 6. Iterate through selected repositories and index files
        for repo_full_name in repo_full_names_to_index:
            if not repo_full_name or not isinstance(repo_full_name, str):
                logger.warning(f"Skipping invalid repository entry: {repo_full_name}")
                continue

            logger.info(f"Processing repository: {repo_full_name}")
            try:
                files_to_index = github_client.get_repository_files(repo_full_name)
                if not files_to_index:
                    logger.info(f"No indexable files found in repository: {repo_full_name}")
                    continue

                logger.info(f"Found {len(files_to_index)} files to process in {repo_full_name}")

                for file_info in files_to_index:
                    file_path = file_info.get("path")
                    file_url = file_info.get("url")
                    file_sha = file_info.get("sha")
                    file_type = file_info.get("type") # 'code' or 'doc'
                    full_path_key = f"{repo_full_name}/{file_path}"

                    if not file_path or not file_url or not file_sha:
                        logger.warning(f"Skipping file with missing info in {repo_full_name}: {file_info}")
                        continue

                    # Get file content
                    file_content = github_client.get_file_content(repo_full_name, file_path)

                    if file_content is None:
                        logger.warning(f"Could not retrieve content for {full_path_key}. Skipping.")
                        continue # Skip if content fetch failed
                        
                    content_hash = generate_content_hash(file_content, search_space_id)

                    # Check if document with this content hash already exists
                    existing_doc_by_hash_result = await session.execute(
                        select(Document).where(Document.content_hash == content_hash)
                    )
                    existing_document_by_hash = existing_doc_by_hash_result.scalars().first()
                    
                    if existing_document_by_hash:
                        logger.info(f"Document with content hash {content_hash} already exists for file {full_path_key}. Skipping processing.")
                        continue
                        
                    # Use file_content directly for chunking, maybe summary for main content?
                    # For now, let's use the full content for both, might need refinement
                    summary_content = f"GitHub file: {full_path_key}\n\n{file_content[:1000]}..." # Simple summary
                    summary_embedding = config.embedding_model_instance.embed(summary_content)

                    # Chunk the content
                    try:
                        chunks_data = [
                            Chunk(content=chunk.text, embedding=config.embedding_model_instance.embed(chunk.text))
                            for chunk in config.code_chunker_instance.chunk(file_content)
                        ]
                    except Exception as chunk_err:
                        logger.error(f"Failed to chunk file {full_path_key}: {chunk_err}")
                        errors.append(f"Chunking failed for {full_path_key}: {chunk_err}")
                        continue # Skip this file if chunking fails

                    doc_metadata = {
                        "repository_full_name": repo_full_name,
                        "file_path": file_path,
                        "full_path": full_path_key, # For easier lookup
                        "url": file_url,
                        "sha": file_sha,
                        "type": file_type,
                        "indexed_at": datetime.now(timezone.utc).isoformat()
                    }

                    # Create new document
                    logger.info(f"Creating new document for file: {full_path_key}")
                    document = Document(
                        title=f"GitHub - {file_path}",
                        document_type=DocumentType.GITHUB_CONNECTOR,
                        document_metadata=doc_metadata,
                        content=summary_content, # Store summary
                        content_hash=content_hash,
                        embedding=summary_embedding,
                        search_space_id=search_space_id,
                        chunks=chunks_data # Associate chunks directly
                    )
                    session.add(document)
                    documents_processed += 1

            except Exception as repo_err:
                logger.error(f"Failed to process repository {repo_full_name}: {repo_err}")
                errors.append(f"Failed processing {repo_full_name}: {repo_err}")
        
        # Commit all changes at the end
        await session.commit()
        logger.info(f"Finished GitHub indexing for connector {connector_id}. Processed {documents_processed} files.")

    except SQLAlchemyError as db_err:
        await session.rollback()
        logger.error(f"Database error during GitHub indexing for connector {connector_id}: {db_err}")
        errors.append(f"Database error: {db_err}")
        return documents_processed, "; ".join(errors) if errors else str(db_err)
    except Exception as e:
        await session.rollback()
        logger.error(f"Unexpected error during GitHub indexing for connector {connector_id}: {e}", exc_info=True)
        errors.append(f"Unexpected error: {e}")
        return documents_processed, "; ".join(errors) if errors else str(e)

    error_message = "; ".join(errors) if errors else None
    return documents_processed, error_message

async def index_linear_issues(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str = None,
    end_date: str = None,
    update_last_indexed: bool = True
) -> Tuple[int, Optional[str]]:
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
    try:
        # Get the connector
        result = await session.execute(
            select(SearchSourceConnector)
            .filter(
                SearchSourceConnector.id == connector_id,
                SearchSourceConnector.connector_type == SearchSourceConnectorType.LINEAR_CONNECTOR
            )
        )
        connector = result.scalars().first()
        
        if not connector:
            return 0, f"Connector with ID {connector_id} not found or is not a Linear connector"
        
        # Get the Linear token from the connector config
        linear_token = connector.config.get("LINEAR_API_KEY")
        if not linear_token:
            return 0, "Linear API token not found in connector config"
        
        # Initialize Linear client
        linear_client = LinearConnector(token=linear_token)
        
        # Calculate date range
        if start_date is None or end_date is None:
            # Fall back to calculating dates based on last_indexed_at
            calculated_end_date = datetime.now()
            
            # Use last_indexed_at as start date if available, otherwise use 365 days ago
            if connector.last_indexed_at:
                # Convert dates to be comparable (both timezone-naive)
                last_indexed_naive = connector.last_indexed_at.replace(tzinfo=None) if connector.last_indexed_at.tzinfo else connector.last_indexed_at
                
                # Check if last_indexed_at is in the future or after end_date
                if last_indexed_naive > calculated_end_date:
                    logger.warning(f"Last indexed date ({last_indexed_naive.strftime('%Y-%m-%d')}) is in the future. Using 365 days ago instead.")
                    calculated_start_date = calculated_end_date - timedelta(days=365)
                else:
                    calculated_start_date = last_indexed_naive
                    logger.info(f"Using last_indexed_at ({calculated_start_date.strftime('%Y-%m-%d')}) as start date")
            else:
                calculated_start_date = calculated_end_date - timedelta(days=365)  # Use 365 days as default
                logger.info(f"No last_indexed_at found, using {calculated_start_date.strftime('%Y-%m-%d')} (365 days ago) as start date")
            
            # Use calculated dates if not provided
            start_date_str = start_date if start_date else calculated_start_date.strftime("%Y-%m-%d")
            end_date_str = end_date if end_date else calculated_end_date.strftime("%Y-%m-%d")
        else:
            # Use provided dates
            start_date_str = start_date
            end_date_str = end_date
        
        logger.info(f"Fetching Linear issues from {start_date_str} to {end_date_str}")
        
        # Get issues within date range
        try:
            issues, error = linear_client.get_issues_by_date_range(
                start_date=start_date_str,
                end_date=end_date_str,
                include_comments=True
            )
            
            if error:
                logger.error(f"Failed to get Linear issues: {error}")
                
                # Don't treat "No issues found" as an error that should stop indexing
                if "No issues found" in error:
                    logger.info("No issues found is not a critical error, continuing with update")
                    if update_last_indexed:
                        connector.last_indexed_at = datetime.now()
                        await session.commit()
                        logger.info(f"Updated last_indexed_at to {connector.last_indexed_at} despite no issues found")
                    return 0, None
                else:
                    return 0, f"Failed to get Linear issues: {error}"
            
            logger.info(f"Retrieved {len(issues)} issues from Linear API")
            
        except Exception as e:
            logger.error(f"Exception when calling Linear API: {str(e)}", exc_info=True)
            return 0, f"Failed to get Linear issues: {str(e)}"
        
        if not issues:
            logger.info("No Linear issues found for the specified date range")
            if update_last_indexed:
                connector.last_indexed_at = datetime.now()
                await session.commit()
                logger.info(f"Updated last_indexed_at to {connector.last_indexed_at} despite no issues found")
            return 0, None  # Return None instead of error message when no issues found
        
        # Log issue IDs and titles for debugging
        logger.info("Issues retrieved from Linear API:")
        for idx, issue in enumerate(issues[:10]):  # Log first 10 issues
            logger.info(f"  {idx+1}. {issue.get('identifier', 'Unknown')} - {issue.get('title', 'Unknown')} - Created: {issue.get('createdAt', 'Unknown')} - Updated: {issue.get('updatedAt', 'Unknown')}")
        if len(issues) > 10:
            logger.info(f"  ...and {len(issues) - 10} more issues")
        
        # Track the number of documents indexed
        documents_indexed = 0
        documents_skipped = 0
        skipped_issues = []
        
        # Process each issue
        for issue in issues:
            try:
                issue_id = issue.get("id")
                issue_identifier = issue.get("identifier", "")
                issue_title = issue.get("title", "")
                
                if not issue_id or not issue_title:
                    logger.warning(f"Skipping issue with missing ID or title: {issue_id or 'Unknown'}")
                    skipped_issues.append(f"{issue_identifier or 'Unknown'} (missing data)")
                    documents_skipped += 1
                    continue
                
                # Format the issue first to get well-structured data
                formatted_issue = linear_client.format_issue(issue)
                
                # Convert issue to markdown format
                issue_content = linear_client.format_issue_to_markdown(formatted_issue)
                
                if not issue_content:
                    logger.warning(f"Skipping issue with no content: {issue_identifier} - {issue_title}")
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
                existing_document_by_hash = existing_doc_by_hash_result.scalars().first()
                
                if existing_document_by_hash:
                    logger.info(f"Document with content hash {content_hash} already exists for issue {issue_identifier}. Skipping processing.")
                    documents_skipped += 1
                    continue
                
                # Generate embedding for the summary
                summary_embedding = config.embedding_model_instance.embed(summary_content)
                
                # Process chunks - using the full issue content with comments
                chunks = [
                    Chunk(content=chunk.text, embedding=config.embedding_model_instance.embed(chunk.text))
                    for chunk in config.chunker_instance.chunk(issue_content)
                ]
                
                # Create and store new document
                logger.info(f"Creating new document for issue {issue_identifier} - {issue_title}")
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
                        "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    },
                    content=summary_content,
                    content_hash=content_hash,
                    embedding=summary_embedding,
                    chunks=chunks
                )
                
                session.add(document)
                documents_indexed += 1
                logger.info(f"Successfully indexed new issue {issue_identifier} - {issue_title}")
                
            except Exception as e:
                logger.error(f"Error processing issue {issue.get('identifier', 'Unknown')}: {str(e)}", exc_info=True)
                skipped_issues.append(f"{issue.get('identifier', 'Unknown')} (processing error)")
                documents_skipped += 1
                continue  # Skip this issue and continue with others
        
        # Update the last_indexed_at timestamp for the connector only if requested
        total_processed = documents_indexed
        if update_last_indexed:
            connector.last_indexed_at = datetime.now()
            logger.info(f"Updated last_indexed_at to {connector.last_indexed_at}")
        
        # Commit all changes
        await session.commit()
        logger.info(f"Successfully committed all Linear document changes to database")
        
       
        logger.info(f"Linear indexing completed: {documents_indexed} new issues, {documents_skipped} skipped")
        return total_processed, None  # Return None as the error message to indicate success
    
    except SQLAlchemyError as db_error:
        await session.rollback()
        logger.error(f"Database error: {str(db_error)}", exc_info=True)
        return 0, f"Database error: {str(db_error)}"
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to index Linear issues: {str(e)}", exc_info=True)
        return 0, f"Failed to index Linear issues: {str(e)}"

async def index_discord_messages(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str = None,
    end_date: str = None,
    update_last_indexed: bool = True
) -> Tuple[int, Optional[str]]:
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
    try:
        # Get the connector
        result = await session.execute(
            select(SearchSourceConnector)
            .filter(
                SearchSourceConnector.id == connector_id,
                SearchSourceConnector.connector_type == SearchSourceConnectorType.DISCORD_CONNECTOR
            )
        )
        connector = result.scalars().first()

        if not connector:
            return 0, f"Connector with ID {connector_id} not found or is not a Discord connector"

        # Get the Discord token from the connector config
        discord_token = connector.config.get("DISCORD_BOT_TOKEN")
        if not discord_token:
            return 0, "Discord token not found in connector config"

        logger.info(f"Starting Discord indexing for connector {connector_id}")

        # Initialize Discord client
        discord_client = DiscordConnector(token=discord_token)

        # Calculate date range
        if start_date is None or end_date is None:
            # Fall back to calculating dates based on last_indexed_at
            calculated_end_date = datetime.now(timezone.utc)

            # Use last_indexed_at as start date if available, otherwise use 365 days ago
            if connector.last_indexed_at:
                calculated_start_date = connector.last_indexed_at.replace(tzinfo=timezone.utc)
                logger.info(f"Using last_indexed_at ({calculated_start_date.strftime('%Y-%m-%d')}) as start date")
            else:
                calculated_start_date = calculated_end_date - timedelta(days=365)
                logger.info(f"No last_indexed_at found, using {calculated_start_date.strftime('%Y-%m-%d')} (365 days ago) as start date")

            # Use calculated dates if not provided, convert to ISO format for Discord API
            if start_date is None:
                start_date_iso = calculated_start_date.isoformat()
            else:
                # Convert YYYY-MM-DD to ISO format
                start_date_iso = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc).isoformat()
                
            if end_date is None:
                end_date_iso = calculated_end_date.isoformat()
            else:
                # Convert YYYY-MM-DD to ISO format  
                end_date_iso = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc).isoformat()
        else:
            # Convert provided dates to ISO format for Discord API
            start_date_iso = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc).isoformat()
            end_date_iso = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc).isoformat()
            
        logger.info(f"Indexing Discord messages from {start_date_iso} to {end_date_iso}")

        documents_indexed = 0
        documents_skipped = 0
        skipped_channels = []

        try:
            logger.info("Starting Discord bot to fetch guilds")
            discord_client._bot_task = asyncio.create_task(discord_client.start_bot())
            await discord_client._wait_until_ready()

            logger.info("Fetching Discord guilds")
            guilds = await discord_client.get_guilds()
            logger.info(f"Found {len(guilds)} guilds")
        except Exception as e:
            logger.error(f"Failed to get Discord guilds: {str(e)}", exc_info=True)
            await discord_client.close_bot()
            return 0, f"Failed to get Discord guilds: {str(e)}"
        if not guilds:
            logger.info("No Discord guilds found to index")
            await discord_client.close_bot()
            return 0, "No Discord guilds found"

        # Process each guild and channel
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
                        logger.error(f"Failed to get messages for channel {channel_name}: {str(e)}")
                        skipped_channels.append(f"{guild_name}#{channel_name} (fetch error)")
                        documents_skipped += 1
                        continue

                    if not messages:
                        logger.info(f"No messages found in channel {channel_name} for the specified date range.")
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
                        logger.info(f"No valid messages found in channel {channel_name} after filtering.")
                        documents_skipped += 1
                        continue

                    # Convert messages to markdown format
                    channel_content = f"# Discord Channel: {guild_name} / {channel_name}\n\n"
                    for msg in formatted_messages:
                        user_name = msg.get("author_name", "Unknown User")
                        timestamp = msg.get("created_at", "Unknown Time")
                        text = msg.get("content", "")
                        channel_content += f"## {user_name} ({timestamp})\n\n{text}\n\n---\n\n"

                    # Format document metadata
                    metadata_sections = [
                        ("METADATA", [
                            f"GUILD_NAME: {guild_name}",
                            f"GUILD_ID: {guild_id}",
                            f"CHANNEL_NAME: {channel_name}",
                            f"CHANNEL_ID: {channel_id}",
                            f"MESSAGE_COUNT: {len(formatted_messages)}"
                        ]),
                        ("CONTENT", [
                            "FORMAT: markdown",
                            "TEXT_START",
                            channel_content,
                            "TEXT_END"
                        ])
                    ]

                    # Build the document string
                    document_parts = []
                    document_parts.append("<DOCUMENT>")
                    for section_title, section_content in metadata_sections:
                        document_parts.append(f"<{section_title}>")
                        document_parts.extend(section_content)
                        document_parts.append(f"</{section_title}>")
                    document_parts.append("</DOCUMENT>")
                    combined_document_string = '\n'.join(document_parts)
                    content_hash = generate_content_hash(combined_document_string, search_space_id)

                    # Check if document with this content hash already exists
                    existing_doc_by_hash_result = await session.execute(
                        select(Document).where(Document.content_hash == content_hash)
                    )
                    existing_document_by_hash = existing_doc_by_hash_result.scalars().first()

                    if existing_document_by_hash:
                        logger.info(f"Document with content hash {content_hash} already exists for channel {guild_name}#{channel_name}. Skipping processing.")
                        documents_skipped += 1
                        continue

                    # Get user's long context LLM
                    user_llm = await get_user_long_context_llm(session, user_id)
                    if not user_llm:
                        logger.error(f"No long context LLM configured for user {user_id}")
                        skipped_channels.append(f"{guild_name}#{channel_name} (no LLM configured)")
                        documents_skipped += 1
                        continue

                    # Generate summary using summary_chain
                    summary_chain = SUMMARY_PROMPT_TEMPLATE | user_llm
                    summary_result = await summary_chain.ainvoke({"document": combined_document_string})
                    summary_content = summary_result.content
                    summary_embedding = await asyncio.to_thread(
                        config.embedding_model_instance.embed, summary_content
                    )

                    # Process chunks
                    raw_chunks = await asyncio.to_thread(
                        config.chunker_instance.chunk,
                        channel_content
                    )

                    chunk_texts = [chunk.text for chunk in raw_chunks if chunk.text.strip()]
                    chunk_embeddings = await asyncio.to_thread(
                        lambda texts: [config.embedding_model_instance.embed(t) for t in texts],
                        chunk_texts
                    )

                    chunks = [
                        Chunk(content=raw_chunk.text, embedding=embedding)
                        for raw_chunk, embedding in zip(raw_chunks, chunk_embeddings)
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
                            "indexed_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                        },
                        content=summary_content,
                        content_hash=content_hash,
                        embedding=summary_embedding,
                        chunks=chunks
                    )

                    session.add(document)
                    documents_indexed += 1
                    logger.info(f"Successfully indexed new channel {guild_name}#{channel_name} with {len(formatted_messages)} messages")

            except Exception as e:
                logger.error(f"Error processing guild {guild_name}: {str(e)}", exc_info=True)
                skipped_channels.append(f"{guild_name} (processing error)")
                documents_skipped += 1
                continue

        if update_last_indexed and documents_indexed > 0:
            connector.last_indexed_at = datetime.now(timezone.utc)
            logger.info(f"Updated last_indexed_at to {connector.last_indexed_at}")

        await session.commit()
        await discord_client.close_bot()

        # Prepare result message
        result_message = None
        if skipped_channels:
            result_message = f"Processed {documents_indexed} channels. Skipped {len(skipped_channels)} channels: {', '.join(skipped_channels)}"
        else:
            result_message = f"Processed {documents_indexed} channels."

        logger.info(f"Discord indexing completed: {documents_indexed} new channels, {documents_skipped} skipped")
        return documents_indexed, result_message

    except SQLAlchemyError as db_error:
        await session.rollback()
        logger.error(f"Database error during Discord indexing: {str(db_error)}", exc_info=True)
        return 0, f"Database error: {str(db_error)}"
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to index Discord messages: {str(e)}", exc_info=True)
        return 0, f"Failed to index Discord messages: {str(e)}"
