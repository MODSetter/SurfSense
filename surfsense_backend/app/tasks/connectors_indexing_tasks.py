from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select
from sqlalchemy import delete
from datetime import datetime, timedelta, timezone
from app.db import Document, DocumentType, Chunk, SearchSourceConnector, SearchSourceConnectorType
from app.config import config
from app.prompts import SUMMARY_PROMPT_TEMPLATE
from app.connectors.slack_history import SlackHistory
from app.connectors.notion_history import NotionHistoryConnector
from app.connectors.github_connector import GitHubConnector
from app.connectors.linear_connector import LinearConnector
from slack_sdk.errors import SlackApiError
import logging

# Set up logging
logger = logging.getLogger(__name__)

async def index_slack_messages(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
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
        end_date = datetime.now()
        
        # Use last_indexed_at as start date if available, otherwise use 365 days ago
        if connector.last_indexed_at:
            # Convert dates to be comparable (both timezone-naive)
            last_indexed_naive = connector.last_indexed_at.replace(tzinfo=None) if connector.last_indexed_at.tzinfo else connector.last_indexed_at
            
            # Check if last_indexed_at is in the future or after end_date
            if last_indexed_naive > end_date:
                logger.warning(f"Last indexed date ({last_indexed_naive.strftime('%Y-%m-%d')}) is in the future. Using 30 days ago instead.")
                start_date = end_date - timedelta(days=30)
            else:
                start_date = last_indexed_naive
                logger.info(f"Using last_indexed_at ({start_date.strftime('%Y-%m-%d')}) as start date")
        else:
            start_date = end_date - timedelta(days=30)  # Use 30 days instead of 365 to catch recent issues
            logger.info(f"No last_indexed_at found, using {start_date.strftime('%Y-%m-%d')} (30 days ago) as start date")
        
        # Format dates for Slack API
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")
        
        # Get all channels
        try:
            channels = slack_client.get_all_channels()
        except Exception as e:
            return 0, f"Failed to get Slack channels: {str(e)}"
        
        if not channels:
            return 0, "No Slack channels found"
            
        # Get existing documents for this search space and connector type to prevent duplicates
        existing_docs_result = await session.execute(
            select(Document)
            .filter(
                Document.search_space_id == search_space_id,
                Document.document_type == DocumentType.SLACK_CONNECTOR
            )
        )
        existing_docs = existing_docs_result.scalars().all()
        
        # Create a lookup dictionary of existing documents by channel_id
        existing_docs_by_channel_id = {}
        for doc in existing_docs:
            if "channel_id" in doc.document_metadata:
                existing_docs_by_channel_id[doc.document_metadata["channel_id"]] = doc
        
        logger.info(f"Found {len(existing_docs_by_channel_id)} existing Slack documents in database")
        
        # Track the number of documents indexed
        documents_indexed = 0
        documents_updated = 0
        documents_skipped = 0
        skipped_channels = []
        
        # Process each channel
        for channel_name, channel_id in channels.items():
            try:
                # Check if the bot is a member of the channel
                try:
                    # First try to get channel info to check if bot is a member
                    channel_info = slack_client.client.conversations_info(channel=channel_id)
                    
                    # For private channels, the bot needs to be a member
                    if channel_info.get("channel", {}).get("is_private", False):
                        # Check if bot is a member
                        is_member = channel_info.get("channel", {}).get("is_member", False)
                        if not is_member:
                            logger.warning(f"Bot is not a member of private channel {channel_name} ({channel_id}). Skipping.")
                            skipped_channels.append(f"{channel_name} (private, bot not a member)")
                            documents_skipped += 1
                            continue
                except SlackApiError as e:
                    if "not_in_channel" in str(e) or "channel_not_found" in str(e):
                        logger.warning(f"Bot cannot access channel {channel_name} ({channel_id}). Skipping.")
                        skipped_channels.append(f"{channel_name} (access error)")
                        documents_skipped += 1
                        continue
                    else:
                        # Re-raise if it's a different error
                        raise
                
                # Get messages for this channel
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
                        f"START_DATE: {start_date_str}",
                        f"END_DATE: {end_date_str}",
                        f"MESSAGE_COUNT: {len(formatted_messages)}",
                        f"INDEXED_AT: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
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
                
                # Generate summary
                summary_chain = SUMMARY_PROMPT_TEMPLATE | config.long_context_llm_instance
                summary_result = await summary_chain.ainvoke({"document": combined_document_string})
                summary_content = summary_result.content
                summary_embedding = config.embedding_model_instance.embed(summary_content)
                
                # Process chunks
                chunks = [
                    Chunk(content=chunk.text, embedding=config.embedding_model_instance.embed(chunk.text))
                    for chunk in config.chunker_instance.chunk(channel_content)
                ]
                
                # Check if this channel already exists in our database
                existing_document = existing_docs_by_channel_id.get(channel_id)
                
                if existing_document:
                    # Update existing document instead of creating a new one
                    logger.info(f"Updating existing document for channel {channel_name}")
                    
                    # Update document fields
                    existing_document.title = f"Slack - {channel_name}"
                    existing_document.document_metadata = {
                        "channel_name": channel_name,
                        "channel_id": channel_id,
                        "start_date": start_date_str,
                        "end_date": end_date_str,
                        "message_count": len(formatted_messages),
                        "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    existing_document.content = summary_content
                    existing_document.embedding = summary_embedding
                    
                    # Delete existing chunks and add new ones
                    await session.execute(
                        delete(Chunk)
                        .where(Chunk.document_id == existing_document.id)
                    )
                    
                    # Assign new chunks to existing document
                    for chunk in chunks:
                        chunk.document_id = existing_document.id
                        session.add(chunk)
                    
                    documents_updated += 1
                else:
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
                        chunks=chunks
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
        total_processed = documents_indexed + documents_updated
        if update_last_indexed and total_processed > 0:
            connector.last_indexed_at = datetime.now()
        
        # Commit all changes
        await session.commit()
        
        # Prepare result message
        result_message = None
        if skipped_channels:
            result_message = f"Processed {total_processed} channels ({documents_indexed} new, {documents_updated} updated). Skipped {len(skipped_channels)} channels: {', '.join(skipped_channels)}"
        else:
            result_message = f"Processed {total_processed} channels ({documents_indexed} new, {documents_updated} updated)."
        
        logger.info(f"Slack indexing completed: {documents_indexed} new channels, {documents_updated} updated, {documents_skipped} skipped")
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
        end_date = datetime.now()
        
        # Check for last 1 year of pages
        start_date = end_date - timedelta(days=365)
        
        # Format dates for Notion API (ISO format)
        start_date_str = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_date_str = end_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        logger.info(f"Fetching Notion pages from {start_date_str} to {end_date_str}")
        
        # Get all pages
        try:
            pages = notion_client.get_all_pages(start_date=start_date_str, end_date=end_date_str)
            logger.info(f"Found {len(pages)} Notion pages")
        except Exception as e:
            logger.error(f"Error fetching Notion pages: {str(e)}", exc_info=True)
            return 0, f"Failed to get Notion pages: {str(e)}"
        
        if not pages:
            logger.info("No Notion pages found to index")
            return 0, "No Notion pages found"
        
        # Get existing documents for this search space and connector type to prevent duplicates
        existing_docs_result = await session.execute(
            select(Document)
            .filter(
                Document.search_space_id == search_space_id,
                Document.document_type == DocumentType.NOTION_CONNECTOR
            )
        )
        existing_docs = existing_docs_result.scalars().all()
        
        # Create a lookup dictionary of existing documents by page_id
        existing_docs_by_page_id = {}
        for doc in existing_docs:
            if "page_id" in doc.document_metadata:
                existing_docs_by_page_id[doc.document_metadata["page_id"]] = doc
        
        logger.info(f"Found {len(existing_docs_by_page_id)} existing Notion documents in database")
        
        # Track the number of documents indexed
        documents_indexed = 0
        documents_updated = 0
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
                        f"PAGE_ID: {page_id}",
                        f"INDEXED_AT: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
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
                
                # Generate summary
                logger.debug(f"Generating summary for page {page_title}")
                summary_chain = SUMMARY_PROMPT_TEMPLATE | config.long_context_llm_instance
                summary_result = await summary_chain.ainvoke({"document": combined_document_string})
                summary_content = summary_result.content
                summary_embedding = config.embedding_model_instance.embed(summary_content)
                
                # Process chunks
                logger.debug(f"Chunking content for page {page_title}")
                chunks = [
                    Chunk(content=chunk.text, embedding=config.embedding_model_instance.embed(chunk.text))
                    for chunk in config.chunker_instance.chunk(markdown_content)
                ]
                
                # Check if this page already exists in our database
                existing_document = existing_docs_by_page_id.get(page_id)
                
                if existing_document:
                    # Update existing document instead of creating a new one
                    logger.info(f"Updating existing document for page {page_title}")
                    
                    # Update document fields
                    existing_document.title = f"Notion - {page_title}"
                    existing_document.document_metadata = {
                        "page_title": page_title,
                        "page_id": page_id,
                        "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    existing_document.content = summary_content
                    existing_document.embedding = summary_embedding
                    
                    # Delete existing chunks and add new ones
                    await session.execute(
                        delete(Chunk)
                        .where(Chunk.document_id == existing_document.id)
                    )
                    
                    # Assign new chunks to existing document
                    for chunk in chunks:
                        chunk.document_id = existing_document.id
                        session.add(chunk)
                    
                    documents_updated += 1
                else:
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
        total_processed = documents_indexed + documents_updated
        if update_last_indexed and total_processed > 0:
            connector.last_indexed_at = datetime.now()
            logger.info(f"Updated last_indexed_at for connector {connector_id}")
        
        # Commit all changes
        await session.commit()
        
        # Prepare result message
        result_message = None
        if skipped_pages:
            result_message = f"Processed {total_processed} pages ({documents_indexed} new, {documents_updated} updated). Skipped {len(skipped_pages)} pages: {', '.join(skipped_pages)}"
        else:
            result_message = f"Processed {total_processed} pages ({documents_indexed} new, {documents_updated} updated)."
        
        logger.info(f"Notion indexing completed: {documents_indexed} new pages, {documents_updated} updated, {documents_skipped} skipped")
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

        # 5. Get existing documents for this search space and connector type to prevent duplicates
        existing_docs_result = await session.execute(
            select(Document)
            .filter(
                Document.search_space_id == search_space_id,
                Document.document_type == DocumentType.GITHUB_CONNECTOR
            )
        )
        existing_docs = existing_docs_result.scalars().all()
        # Create a lookup dict: key=repo_fullname/file_path, value=Document object
        existing_docs_lookup = {doc.document_metadata.get("full_path"): doc for doc in existing_docs if doc.document_metadata.get("full_path")}
        logger.info(f"Found {len(existing_docs_lookup)} existing GitHub documents in database for search space {search_space_id}")

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

                    # Check if document already exists and if content hash matches
                    existing_doc = existing_docs_lookup.get(full_path_key)
                    if existing_doc and existing_doc.document_metadata.get("sha") == file_sha:
                        logger.debug(f"Skipping unchanged file: {full_path_key}")
                        continue # Skip if SHA matches (content hasn't changed)

                    # Get file content
                    file_content = github_client.get_file_content(repo_full_name, file_path)

                    if file_content is None:
                        logger.warning(f"Could not retrieve content for {full_path_key}. Skipping.")
                        continue # Skip if content fetch failed
                        
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

                    if existing_doc:
                        # Update existing document
                        logger.info(f"Updating document for file: {full_path_key}")
                        existing_doc.title = f"GitHub - {file_path}"
                        existing_doc.document_metadata = doc_metadata
                        existing_doc.content = summary_content # Update summary
                        existing_doc.embedding = summary_embedding # Update embedding

                        # Delete old chunks
                        await session.execute(
                            delete(Chunk)
                            .where(Chunk.document_id == existing_doc.id)
                        )
                        # Add new chunks
                        for chunk_obj in chunks_data:
                            chunk_obj.document_id = existing_doc.id
                            session.add(chunk_obj)
                        
                        documents_processed += 1
                    else:
                        # Create new document
                        logger.info(f"Creating new document for file: {full_path_key}")
                        document = Document(
                            title=f"GitHub - {file_path}",
                            document_type=DocumentType.GITHUB_CONNECTOR,
                            document_metadata=doc_metadata,
                            content=summary_content, # Store summary
                            embedding=summary_embedding,
                            search_space_id=search_space_id,
                            chunks=chunks_data # Associate chunks directly
                        )
                        session.add(document)
                        documents_processed += 1

                    # Commit periodically or at the end? For now, commit per repo
                    # await session.commit() 

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
        end_date = datetime.now()
        
        # Use last_indexed_at as start date if available, otherwise use 365 days ago
        if connector.last_indexed_at:
            # Convert dates to be comparable (both timezone-naive)
            last_indexed_naive = connector.last_indexed_at.replace(tzinfo=None) if connector.last_indexed_at.tzinfo else connector.last_indexed_at
            
            # Check if last_indexed_at is in the future or after end_date
            if last_indexed_naive > end_date:
                logger.warning(f"Last indexed date ({last_indexed_naive.strftime('%Y-%m-%d')}) is in the future. Using 30 days ago instead.")
                start_date = end_date - timedelta(days=30)
            else:
                start_date = last_indexed_naive
                logger.info(f"Using last_indexed_at ({start_date.strftime('%Y-%m-%d')}) as start date")
        else:
            start_date = end_date - timedelta(days=30)  # Use 30 days instead of 365 to catch recent issues
            logger.info(f"No last_indexed_at found, using {start_date.strftime('%Y-%m-%d')} (30 days ago) as start date")
        
        # Format dates for Linear API
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")
        
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
        
        # Get existing documents for this search space and connector type to prevent duplicates
        existing_docs_result = await session.execute(
            select(Document)
            .filter(
                Document.search_space_id == search_space_id,
                Document.document_type == DocumentType.LINEAR_CONNECTOR
            )
        )
        existing_docs = existing_docs_result.scalars().all()
        
        # Create a lookup dictionary of existing documents by issue_id
        existing_docs_by_issue_id = {}
        for doc in existing_docs:
            if "issue_id" in doc.document_metadata:
                existing_docs_by_issue_id[doc.document_metadata["issue_id"]] = doc
        
        logger.info(f"Found {len(existing_docs_by_issue_id)} existing Linear documents in database")
        
        # Log existing document IDs for debugging
        if existing_docs_by_issue_id:
            logger.info("Existing Linear document issue IDs in database:")
            for idx, (issue_id, doc) in enumerate(list(existing_docs_by_issue_id.items())[:10]):  # Log first 10
                logger.info(f"  {idx+1}. {issue_id} - {doc.document_metadata.get('issue_identifier', 'Unknown')} - {doc.document_metadata.get('issue_title', 'Unknown')}")
            if len(existing_docs_by_issue_id) > 10:
                logger.info(f"  ...and {len(existing_docs_by_issue_id) - 10} more existing documents")
        
        # Track the number of documents indexed
        documents_indexed = 0
        documents_updated = 0
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
                
                # Generate embedding for the summary
                summary_embedding = config.embedding_model_instance.embed(summary_content)
                
                # Process chunks - using the full issue content with comments
                chunks = [
                    Chunk(content=chunk.text, embedding=config.embedding_model_instance.embed(chunk.text))
                    for chunk in config.chunker_instance.chunk(issue_content)
                ]
                
                # Check if this issue already exists in our database
                existing_document = existing_docs_by_issue_id.get(issue_id)
                
                if existing_document:
                    # Update existing document instead of creating a new one
                    logger.info(f"Updating existing document for issue {issue_identifier} - {issue_title}")
                    
                    # Update document fields
                    existing_document.title = f"Linear - {issue_identifier}: {issue_title}"
                    existing_document.document_metadata = {
                        "issue_id": issue_id,
                        "issue_identifier": issue_identifier,
                        "issue_title": issue_title,
                        "state": state,
                        "comment_count": comment_count,
                        "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    existing_document.content = summary_content
                    existing_document.embedding = summary_embedding
                    
                    # Delete existing chunks and add new ones
                    await session.execute(
                        delete(Chunk)
                        .where(Chunk.document_id == existing_document.id)
                    )
                    
                    # Assign new chunks to existing document
                    for chunk in chunks:
                        chunk.document_id = existing_document.id
                        session.add(chunk)
                    
                    documents_updated += 1
                else:
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
        total_processed = documents_indexed + documents_updated
        if update_last_indexed:
            connector.last_indexed_at = datetime.now()
            logger.info(f"Updated last_indexed_at to {connector.last_indexed_at}")
        
        # Commit all changes
        await session.commit()
        logger.info(f"Successfully committed all Linear document changes to database")
        
       
        logger.info(f"Linear indexing completed: {documents_indexed} new issues, {documents_updated} updated, {documents_skipped} skipped")
        return total_processed, None  # Return None as the error message to indicate success
    
    except SQLAlchemyError as db_error:
        await session.rollback()
        logger.error(f"Database error: {str(db_error)}", exc_info=True)
        return 0, f"Database error: {str(db_error)}"
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to index Linear issues: {str(e)}", exc_info=True)
        return 0, f"Failed to index Linear issues: {str(e)}"
