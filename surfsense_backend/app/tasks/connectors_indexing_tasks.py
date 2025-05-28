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

from typing import Optional, Tuple, List # Added List

async def index_slack_messages(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    update_last_indexed: bool = True,
    target_channel_ids: Optional[List[str]] = None,
    force_reindex_all_messages: bool = False,
    reindex_start_date_str: Optional[str] = None, # Format: YYYY-MM-DD
    reindex_latest_date_str: Optional[str] = None  # Format: YYYY-MM-DD
) -> Tuple[int, Optional[str]]:
    """
    Index Slack messages from all accessible channels.
    
    Args:
        session: Database session
        connector_id: ID of the Slack connector
        search_space_id: ID of the search space to store documents in
        update_last_indexed: Whether to update the last_indexed_at timestamp (default: True)
        target_channel_ids: Optional list of channel IDs to specifically re-index.
        force_reindex_all_messages: If True and target_channel_ids is set, re-fetches all history for target channels.
        reindex_start_date_str: Start date for targeted re-indexing (YYYY-MM-DD).
        reindex_latest_date_str: Latest date for targeted re-indexing (YYYY-MM-DD).
        
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
        
        config_values = connector.config or {}
        slack_membership_filter_type = config_values.get("slack_membership_filter_type", "all_member_channels")
        slack_selected_channel_ids = config_values.get("slack_selected_channel_ids", [])
        slack_selected_channel_ids_set = set(slack_selected_channel_ids) 
        
        default_initial_days = config_values.get("slack_initial_indexing_days", 30)
        default_max_messages_initial = config_values.get("slack_initial_max_messages_per_channel", 1000)
        default_max_messages_periodic = config_values.get("slack_max_messages_per_channel_periodic", 100)

        # Initialize Slack client
        slack_client = SlackHistory(token=slack_token)

        # Determine run type for logging
        run_type_log_message = f"Starting Slack indexing for connector_id={connector_id}, search_space_id={search_space_id}."
        if target_channel_ids:
            run_type_log_message += f" Targeted re-index for {len(target_channel_ids)} channels."
            if force_reindex_all_messages:
                run_type_log_message += " Full history re-index forced."
            else:
                run_type_log_message += " Standard update for targeted channels."
            if reindex_start_date_str:
                run_type_log_message += f" Custom start date: {reindex_start_date_str}."
            if reindex_latest_date_str:
                run_type_log_message += f" Custom latest date: {reindex_latest_date_str}."
        elif force_reindex_all_messages: # Implies full re-index of all configured channels
             run_type_log_message += " Full history re-index for all configured channels."
        else:
            run_type_log_message += " Periodic update for all configured channels."
        
        logger.info(run_type_log_message)
        logger.info(
            f"Base Config: filter_type='{slack_membership_filter_type}', "
            f"num_selected_channels_in_config={len(slack_selected_channel_ids_set) if slack_selected_channel_ids_set else 'N/A'}, "
            f"initial_days_config={default_initial_days}, "
            f"initial_max_messages_config={default_max_messages_initial}, "
            f"periodic_max_messages_config={default_max_messages_periodic}, "
            f"update_last_indexed_param={update_last_indexed}"
        )
        
        if not slack_token:
            return 0, "Slack token not found in connector config"

        # Get all channels from Slack API based on initial membership configuration
        try:
            all_channels_from_api = slack_client.get_all_channels()
        except Exception as e:
            return 0, f"Failed to get Slack channels: {str(e)}"
        
        if not all_channels_from_api:
            logger.info(f"No channels returned by get_all_channels for connector {connector_id}.")
            return 0, "No Slack channels found"

        original_channel_count = len(all_channels_from_api)
        logger.info(f"Found {original_channel_count} total channels accessible by the bot for connector {connector_id} via API.")

        pre_target_channels_to_process = [] # Channels after initial filtering, before target_channel_ids
        if slack_membership_filter_type == "selected_member_channels":
            logger.info(f"Filtering channels based on 'selected_member_channels' list (configured with {len(slack_selected_channel_ids_set)} selected IDs).")
            def get_channel_display_name(channel_obj):
                name = channel_obj.get('name')
                channel_id_local = channel_obj.get('id')
                return name if name else f"ID:{channel_id_local}"

            for channel_obj_loop in all_channels_from_api:
                channel_id_loop = channel_obj_loop.get("id")
                if channel_id_loop in slack_selected_channel_ids_set:
                    pre_target_channels_to_process.append(channel_obj_loop)
                else:
                    logger.debug(f"Channel '{get_channel_display_name(channel_obj_loop)}' ({channel_id_loop}) skipped: not in 'slack_selected_channel_ids' config.")
            logger.info(f"{len(pre_target_channels_to_process)} channels remaining after 'selected_member_channels' filter (originally {original_channel_count}).")
        elif slack_membership_filter_type == "all_member_channels":
            logger.info(f"Processing all {original_channel_count} channels where bot is a member (filter_type='all_member_channels').")
            pre_target_channels_to_process = all_channels_from_api
        
        # Now, if target_channel_ids is provided, further filter channels_to_process
        channels_to_process = []
        if target_channel_ids:
            logger.info(f"Further filtering based on provided `target_channel_ids` list ({len(target_channel_ids)} IDs).")
            target_channel_ids_set = set(target_channel_ids)
            for channel_obj in pre_target_channels_to_process:
                if channel_obj.get("id") in target_channel_ids_set:
                    channels_to_process.append(channel_obj)
            logger.info(f"{len(channels_to_process)} channels remaining after `target_channel_ids` filter (originally {len(pre_target_channels_to_process)} after initial filters).")
        else:
            channels_to_process = pre_target_channels_to_process

        if not channels_to_process:
            logger.info(f"No channels remaining after applying all filters for connector {connector_id}. Nothing to index.")
            if update_last_indexed: # Still update last_indexed if no channels, as the task ran.
                connector.last_indexed_at = datetime.now(timezone.utc) # Use timezone aware datetime
                try:
                    await session.commit()
                    logger.info(f"Connector {connector_id} last_indexed_at updated as no channels were left after filtering.")
                except SQLAlchemyError as db_error_commit:
                    await session.rollback()
                    logger.error(f"Database error while updating last_indexed_at for connector {connector_id} with no channels: {str(db_error_commit)}")
                    return 0, f"DB error updating last_indexed_at: {str(db_error_commit)}"
            return 0, "No channels to index after filtering."
            
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
            if "channel_id" in doc.document_metadata: # Ensure metadata exists and has channel_id
                existing_docs_by_channel_id[doc.document_metadata["channel_id"]] = doc
        
        logger.info(f"Found {len(existing_docs_by_channel_id)} existing Slack documents in database for this search space.")
        
        # Track the number of documents indexed
        documents_indexed = 0
        documents_updated = 0
        documents_skipped = 0
        skipped_channels_log_details = [] # Store details for logging

        # Process each channel
        for channel_obj in channels_to_process:
            channel_id = channel_obj["id"]
            channel_name = channel_obj.get("name", f"Unknown Channel ({channel_id})") # Use .get for safety
            # is_private = channel_obj.get("is_private", False) # Not strictly needed for logic below
            is_member = channel_obj.get("is_member", False) 

            # Determine date range and limit PER CHANNEL based on new logic
            current_channel_is_targeted = target_channel_ids and channel_id in target_channel_ids
            
            # Date/Time Logic for API and Metadata
            # These will be determined per channel now
            oldest_ts_for_api = None # Unix timestamp string or "0"
            latest_ts_for_api = None # Unix timestamp string
            limit_for_api_channel = default_max_messages_periodic # Default for periodic
            start_date_str_metadata_channel = datetime.now(timezone.utc).strftime("%Y-%m-%d") # Default, updated below
            latest_date_str_metadata_channel = datetime.now(timezone.utc).strftime("%Y-%m-%d")


            if current_channel_is_targeted and force_reindex_all_messages:
                logger.info(f"Channel {channel_name} ({channel_id}): Targeted full re-index. Ignoring last_indexed_at.")
                limit_for_api_channel = default_max_messages_initial
                if reindex_start_date_str:
                    try:
                        oldest_ts_for_api = SlackHistory.convert_date_to_timestamp(reindex_start_date_str)
                        start_date_str_metadata_channel = reindex_start_date_str
                    except ValueError:
                        logger.warning(f"Invalid reindex_start_date_str: {reindex_start_date_str}. Falling back to initial days logic for channel {channel_id}.")
                        # Fallback logic
                        if default_initial_days == -1:
                            oldest_ts_for_api = "0"
                            start_date_str_metadata_channel = "all_time"
                        else:
                            start_dt_calc = datetime.now(timezone.utc) - timedelta(days=default_initial_days)
                            oldest_ts_for_api = str(int(start_dt_calc.timestamp()))
                            start_date_str_metadata_channel = start_dt_calc.strftime("%Y-%m-%d")
                elif default_initial_days == -1: # No reindex_start_date_str, use connector initial config
                    oldest_ts_for_api = "0"
                    start_date_str_metadata_channel = "all_time"
                else: # No reindex_start_date_str, use connector initial config (days)
                    start_dt_calc = datetime.now(timezone.utc) - timedelta(days=default_initial_days)
                    oldest_ts_for_api = str(int(start_dt_calc.timestamp()))
                    start_date_str_metadata_channel = start_dt_calc.strftime("%Y-%m-%d")

                if reindex_latest_date_str:
                    try:
                        latest_ts_for_api = SlackHistory.convert_date_to_timestamp(reindex_latest_date_str, is_latest=True)
                        latest_date_str_metadata_channel = reindex_latest_date_str
                    except ValueError:
                        logger.warning(f"Invalid reindex_latest_date_str: {reindex_latest_date_str}. Defaulting to now for channel {channel_id}.")
                        latest_ts_for_api = str(int((datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()))
                        latest_date_str_metadata_channel = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                else: # Default to now if reindex_latest_date_str not provided
                    latest_ts_for_api = str(int((datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()))
                    latest_date_str_metadata_channel = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            elif current_channel_is_targeted: # Targeted but not forced full re-index
                logger.info(f"Channel {channel_name} ({channel_id}): Targeted standard update.")
                limit_for_api_channel = default_max_messages_periodic
                if reindex_start_date_str:
                    try:
                        oldest_ts_for_api = SlackHistory.convert_date_to_timestamp(reindex_start_date_str)
                        start_date_str_metadata_channel = reindex_start_date_str
                    except ValueError:
                        logger.warning(f"Invalid reindex_start_date_str: {reindex_start_date_str} for targeted update. Using connector's last_indexed_at for channel {channel_id}.")
                        if connector.last_indexed_at:
                            oldest_ts_for_api = str(int(connector.last_indexed_at.timestamp()))
                            start_date_str_metadata_channel = connector.last_indexed_at.strftime("%Y-%m-%d")
                        else: # Fallback to initial days if last_indexed_at is also missing
                            start_dt_calc = datetime.now(timezone.utc) - timedelta(days=default_initial_days)
                            oldest_ts_for_api = str(int(start_dt_calc.timestamp()))
                            start_date_str_metadata_channel = start_dt_calc.strftime("%Y-%m-%d")
                elif connector.last_indexed_at:
                    oldest_ts_for_api = str(int(connector.last_indexed_at.timestamp()))
                    start_date_str_metadata_channel = connector.last_indexed_at.strftime("%Y-%m-%d")
                else: # Initial run logic for this targeted channel (no last_indexed_at, no reindex_start_date_str)
                    logger.info(f"Channel {channel_name} ({channel_id}): Targeted, but no reindex_start_date and no connector.last_indexed_at. Applying initial indexing logic.")
                    limit_for_api_channel = default_max_messages_initial # Use initial limit here
                    if default_initial_days == -1:
                        oldest_ts_for_api = "0"
                        start_date_str_metadata_channel = "all_time"
                    else:
                        start_dt_calc = datetime.now(timezone.utc) - timedelta(days=default_initial_days)
                        oldest_ts_for_api = str(int(start_dt_calc.timestamp()))
                        start_date_str_metadata_channel = start_dt_calc.strftime("%Y-%m-%d")
                
                if reindex_latest_date_str: # User can cap the latest date for targeted standard update
                    try:
                        latest_ts_for_api = SlackHistory.convert_date_to_timestamp(reindex_latest_date_str, is_latest=True)
                        latest_date_str_metadata_channel = reindex_latest_date_str
                    except ValueError:
                        logger.warning(f"Invalid reindex_latest_date_str: {reindex_latest_date_str}. Defaulting to now for channel {channel_id}.")
                        latest_ts_for_api = str(int((datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()))
                        latest_date_str_metadata_channel = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                else: # Default to now
                    latest_ts_for_api = str(int((datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()))
                    latest_date_str_metadata_channel = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            else: # Standard run (not targeted specifically for this channel, could be part of a full run)
                is_initial_run_connector = not connector.last_indexed_at
                if force_reindex_all_messages: # Full re-index of all configured channels
                    logger.info(f"Channel {channel_name} ({channel_id}): Part of full history re-index for all channels.")
                    limit_for_api_channel = default_max_messages_initial
                    if default_initial_days == -1: # All time
                        oldest_ts_for_api = "0"
                        start_date_str_metadata_channel = "all_time"
                    else: # Specific number of days
                        start_dt_calc = datetime.now(timezone.utc) - timedelta(days=default_initial_days)
                        oldest_ts_for_api = str(int(start_dt_calc.timestamp()))
                        start_date_str_metadata_channel = start_dt_calc.strftime("%Y-%m-%d")
                    latest_ts_for_api = str(int((datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()))
                    latest_date_str_metadata_channel = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                elif is_initial_run_connector:
                    logger.info(f"Channel {channel_name} ({channel_id}): Connector initial run.")
                    limit_for_api_channel = default_max_messages_initial
                    if default_initial_days == -1:
                        oldest_ts_for_api = "0"
                        start_date_str_metadata_channel = "all_time"
                    else:
                        start_dt_calc = datetime.now(timezone.utc) - timedelta(days=default_initial_days)
                        oldest_ts_for_api = str(int(start_dt_calc.timestamp()))
                        start_date_str_metadata_channel = start_dt_calc.strftime("%Y-%m-%d")
                    latest_ts_for_api = str(int((datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()))
                    latest_date_str_metadata_channel = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                else: # Standard periodic update for this channel
                    logger.info(f"Channel {channel_name} ({channel_id}): Standard periodic update.")
                    limit_for_api_channel = default_max_messages_periodic
                    # Use last_indexed_at, ensuring it's timezone-aware or converted correctly
                    last_indexed_dt_utc = connector.last_indexed_at
                    if last_indexed_dt_utc.tzinfo is None: # If naive, assume UTC
                        last_indexed_dt_utc = last_indexed_dt_utc.replace(tzinfo=timezone.utc)
                    
                    # Check if last_indexed_at is in the future relative to now_utc
                    now_utc = datetime.now(timezone.utc)
                    if last_indexed_dt_utc > now_utc:
                        logger.warning(f"Last indexed date ({last_indexed_dt_utc.strftime('%Y-%m-%d')}) for connector {connector_id} is in the future. Using {default_initial_days} days ago from now instead.")
                        start_dt_calc = now_utc - timedelta(days=default_initial_days)
                    else:
                        start_dt_calc = last_indexed_dt_utc
                    
                    oldest_ts_for_api = str(int(start_dt_calc.timestamp()))
                    start_date_str_metadata_channel = start_dt_calc.strftime("%Y-%m-%d")
                    latest_ts_for_api = str(int((now_utc + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()))
                    latest_date_str_metadata_channel = now_utc.strftime("%Y-%m-%d")

            logger.info(f"For channel {channel_name} ({channel_id}): oldest_ts='{oldest_ts_for_api}', latest_ts='{latest_ts_for_api}', limit={limit_for_api_channel}, start_date_meta='{start_date_str_metadata_channel}', latest_date_meta='{latest_date_str_metadata_channel}'")

            try:
                if not is_member:
                    logger.info(f"Channel {channel_name} ({channel_id}) listed, but bot is_member={is_member}. API call to history will confirm access.")

                # Get messages for this channel
                try:
                    messages = slack_client.get_conversation_history(
                        channel_id=channel_id,
                        limit=limit_for_api_channel, 
                        oldest=oldest_ts_for_api, 
                        latest=latest_ts_for_api 
                    )
                except SlackApiError as slack_api_err:
                    err_msg = slack_api_err.response['error'] if slack_api_err.response and 'error' in slack_api_err.response else str(slack_api_err)
                    if err_msg == 'not_in_channel':
                        logger.warning(f"Bot is not in channel {channel_name} ({channel_id}) or history is private. Skipping. Error: {err_msg}")
                        skipped_channels_log_details.append(f"{channel_name} (not in channel/private history)")
                    else:
                        logger.warning(f"Slack API error for channel {channel_name} ({channel_id}): {err_msg}. Skipping.")
                        skipped_channels_log_details.append(f"{channel_name} (API error: {err_msg})")
                    documents_skipped += 1
                    continue
                except Exception as general_err: 
                    logger.error(f"Unexpected error getting messages from channel {channel_name} ({channel_id}): {str(general_err)}")
                    skipped_channels_log_details.append(f"{channel_name} (Unexpected error: {str(general_err)})")
                    documents_skipped += 1
                    continue
                
                if not messages:
                    logger.info(f"No messages found in channel {channel_name} ({channel_id}) for API params (oldest: {oldest_ts_for_api}, latest: {latest_ts_for_api}, limit: {limit_for_api_channel}).")
                    continue 
                
                # Format messages with user info
                formatted_messages = []
                for msg in messages:
                    if msg.get("subtype") in ["bot_message", "channel_join", "channel_leave"]:
                        continue
                    formatted_msg = slack_client.format_message(msg, include_user_info=True)
                    formatted_messages.append(formatted_msg)
                
                if not formatted_messages:
                    logger.info(f"No valid messages found in channel {channel_name} ({channel_id}) after filtering bot/system messages.")
                    # Do not increment documents_skipped here, it's normal for a channel to have no user messages in a period
                    continue
                
                channel_content = f"# Slack Channel: {channel_name}\n\n"
                for msg in formatted_messages:
                    user_name = msg.get("user_name", "Unknown User")
                    timestamp_str = msg.get("datetime", "Unknown Time") # datetime is already string
                    text = msg.get("text", "")
                    channel_content += f"## {user_name} ({timestamp_str})\n\n{text}\n\n---\n\n"
                
                now_iso_for_metadata = datetime.now(timezone.utc).isoformat()
                metadata_sections = [
                    ("METADATA", [
                        f"CHANNEL_NAME: {channel_name}",
                        f"CHANNEL_ID: {channel_id}",
                        f"START_DATE: {start_date_str_metadata_channel}", 
                        f"END_DATE: {latest_date_str_metadata_channel}",   
                        f"MESSAGE_COUNT: {len(formatted_messages)}",
                        f"INDEXED_AT: {now_iso_for_metadata}"
                    ]),
                    ("CONTENT", ["FORMAT: markdown", "TEXT_START", channel_content, "TEXT_END"])
                ]
                
                document_parts = ["<DOCUMENT>"]
                for section_title, section_content_list in metadata_sections:
                    document_parts.append(f"<{section_title}>")
                    document_parts.extend(section_content_list)
                    document_parts.append(f"</{section_title}>")
                document_parts.append("</DOCUMENT>")
                combined_document_string = '\n'.join(document_parts)
                
                summary_chain = SUMMARY_PROMPT_TEMPLATE | config.long_context_llm_instance
                summary_result = await summary_chain.ainvoke({"document": combined_document_string})
                summary_content = summary_result.content
                summary_embedding = config.embedding_model_instance.embed(summary_content)
                
                doc_chunks = [
                    Chunk(content=chunk_text.text, embedding=config.embedding_model_instance.embed(chunk_text.text))
                    for chunk_text in config.chunker_instance.chunk(channel_content)
                ]
                
                current_doc_metadata = {
                    "channel_name": channel_name,
                    "channel_id": channel_id,
                    "start_date": start_date_str_metadata_channel, 
                    "end_date": latest_date_str_metadata_channel,   
                    "message_count": len(formatted_messages),
                    "indexed_at": now_iso_for_metadata
                }

                existing_document = existing_docs_by_channel_id.get(channel_id)
                if existing_document:
                    logger.info(f"Updating existing document for channel {channel_name} ({channel_id})")
                    existing_document.title = f"Slack - {channel_name}"
                    current_doc_metadata["last_updated"] = now_iso_for_metadata
                    existing_document.document_metadata = current_doc_metadata
                    existing_document.content = summary_content
                    existing_document.embedding = summary_embedding
                    
                    await session.execute(delete(Chunk).where(Chunk.document_id == existing_document.id))
                    for chunk_item in doc_chunks:
                        chunk_item.document_id = existing_document.id
                        session.add(chunk_item)
                    documents_updated += 1
                else:
                    logger.info(f"Creating new document for channel {channel_name} ({channel_id})")
                    document = Document(
                        search_space_id=search_space_id,
                        title=f"Slack - {channel_name}",
                        document_type=DocumentType.SLACK_CONNECTOR,
                        document_metadata=current_doc_metadata,
                        content=summary_content,
                        embedding=summary_embedding,
                        chunks=doc_chunks
                    )
                    session.add(document)
                    documents_indexed += 1
                
            except SlackApiError as slack_error_channel: # Catch API errors per channel
                logger.error(f"Slack API error processing channel {channel_name} ({channel_id}): {str(slack_error_channel)}")
                skipped_channels_log_details.append(f"{channel_name} (Slack API error: {str(slack_error_channel)})")
                documents_skipped += 1
                continue 
            except Exception as e_channel: # Catch other errors per channel
                logger.error(f"Error processing channel {channel_name} ({channel_id}): {str(e_channel)}", exc_info=True)
                skipped_channels_log_details.append(f"{channel_name} (processing error: {str(e_channel)})")
                documents_skipped += 1
                continue 
        
        total_docs_affected = documents_indexed + documents_updated
        if update_last_indexed and (total_docs_affected > 0 or not channels_to_process): # Update if docs changed or if no channels to begin with
            # For targeted re-indexing, last_indexed_at for the connector should still be updated if the overall operation is successful.
            # The new "now" should be after all messages have been fetched.
            connector.last_indexed_at = datetime.now(timezone.utc) 
            logger.info(f"Connector {connector_id} last_indexed_at will be updated to {connector.last_indexed_at.isoformat()}")
        
        await session.commit()
        
        result_summary_message = f"Slack indexing completed for connector {connector_id}: " \
                                 f"{documents_indexed} new, {documents_updated} updated, {documents_skipped} skipped. "
        if skipped_channels_log_details:
            result_summary_message += f"Skipped channels details: {'; '.join(skipped_channels_log_details)}"
        
        logger.info(result_summary_message)
        return total_docs_affected, result_summary_message if documents_skipped > 0 else None # Return None if no errors/skips
    
    except SQLAlchemyError as db_error:
        await session.rollback()
        logger.error(f"Database error during Slack indexing for connector {connector_id}: {str(db_error)}", exc_info=True)
        return 0, f"Database error: {str(db_error)}"
    except Exception as e:
        await session.rollback() # Rollback on any other unexpected error
        logger.error(f"Failed to index Slack messages for connector {connector_id}: {str(e)}", exc_info=True)
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
