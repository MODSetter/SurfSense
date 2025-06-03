"""
Slack History Module

A module for retrieving conversation history from Slack channels.
Allows fetching channel lists and message history with date range filtering.
"""

import time # Added import
import logging # Added import
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__) # Added logger


class SlackHistory:
    """Class for retrieving conversation history from Slack channels."""
    
    def __init__(self, token: str = None):
        """
        Initialize the SlackHistory class.
        
        Args:
            token: Slack API token (optional, can be set later with set_token)
        """
        self.client = WebClient(token=token) if token else None
    
    def set_token(self, token: str) -> None:
        """
        Set the Slack API token.
        
        Args:
            token: Slack API token
        """
        self.client = WebClient(token=token)
    
    def get_all_channels(self, include_private: bool = True) -> List[Dict[str, Any]]:
        """
        Fetch all channels that the bot has access to, with rate limit handling.
        
        Args:
            include_private: Whether to include private channels
        
        Returns:
            List of dictionaries, each representing a channel with id, name, is_private, is_member.
        
        Raises:
            ValueError: If no Slack client has been initialized
            SlackApiError: If there's an unrecoverable error calling the Slack API
            RuntimeError: For unexpected errors during channel fetching.
        """
        if not self.client:
            raise ValueError("Slack client not initialized. Call set_token() first.")
        
        channels_list = [] # Changed from dict to list
        types = "public_channel"
        if include_private:
            types += ",private_channel"

        next_cursor = None
        is_first_request = True

        while is_first_request or next_cursor:
            try:
                if not is_first_request:  # Add delay only for paginated requests
                    logger.info(f"Paginating for channels, waiting 3 seconds before next call. Cursor: {next_cursor}")
                    time.sleep(3)

                current_limit = 1000  # Max limit
                api_result = self.client.conversations_list(
                    types=types,
                    cursor=next_cursor,
                    limit=current_limit
                )
                
                channels_on_page = api_result["channels"]
                for channel in channels_on_page:
                    if "name" in channel and "id" in channel:
                        channel_data = {
                            "id": channel.get("id"),
                            "name": channel.get("name"),
                            "is_private": channel.get("is_private", False),
                            # is_member is often part of the channel object from conversations.list
                            # It indicates if the authenticated user (bot) is a member.
                            # For public channels, this might be true or the API might not focus on it
                            # if the bot can read it anyway. For private, it's crucial.
                            "is_member": channel.get("is_member", False) 
                        }
                        channels_list.append(channel_data)
                    else:
                        logger.warning(f"Channel found with missing name or id. Data: {channel}")


                next_cursor = api_result.get("response_metadata", {}).get("next_cursor")
                is_first_request = False  # Subsequent requests are not the first

                if not next_cursor:  # All pages processed
                    break

            except SlackApiError as e:
                if e.response is not None and e.response.status_code == 429:
                    retry_after_header = e.response.headers.get('Retry-After')
                    wait_duration = 60  # Default wait time
                    if retry_after_header and retry_after_header.isdigit():
                        wait_duration = int(retry_after_header)
                    
                    logger.warning(f"Slack API rate limit hit while fetching channels. Waiting for {wait_duration} seconds. Cursor: {next_cursor}")
                    time.sleep(wait_duration)
                    # The loop will continue, retrying with the same cursor
                else:
                    # Not a 429 error, or no response object, re-raise
                    raise SlackApiError(f"Error retrieving channels: {e}", e.response)
            except Exception as general_error:
                # Handle other potential errors like network issues if necessary, or re-raise
                logger.error(f"An unexpected error occurred during channel fetching: {general_error}")
                raise RuntimeError(f"An unexpected error occurred during channel fetching: {general_error}")
        
        return channels_list
    
    def get_conversation_history(
        self, 
        channel_id: str, 
        limit: int = 1000, 
        oldest: Optional[int] = None, 
        latest: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch conversation history for a channel.
        
        Args:
            channel_id: The ID of the channel to fetch history for
            limit: Maximum number of messages to return per request (default 1000)
            oldest: Start of time range (Unix timestamp)
            latest: End of time range (Unix timestamp)
        
        Returns:
            List of message objects
        
        Raises:
            ValueError: If no Slack client has been initialized
            SlackApiError: If there's an error calling the Slack API
        """
        if not self.client:
            raise ValueError("Slack client not initialized. Call set_token() first.")
        
        messages = []
        next_cursor = None
        
        while True:
            try:
                # Proactive delay for conversations.history (Tier 3)
                time.sleep(1.2) # Wait 1.2 seconds before each history call.

                kwargs = {
                    "channel": channel_id,
                    "limit": min(limit, 1000),  # API max is 1000
                }
                if oldest:
                    kwargs["oldest"] = oldest
                if latest:
                    kwargs["latest"] = latest
                if next_cursor:
                    kwargs["cursor"] = next_cursor
                
                current_api_call_successful = False
                result = None # Ensure result is defined
                try:
                    result = self.client.conversations_history(**kwargs)
                    current_api_call_successful = True
                except SlackApiError as e_history:
                    if e_history.response is not None and e_history.response.status_code == 429:
                        retry_after_str = e_history.response.headers.get('Retry-After')
                        wait_time = 60 # Default
                        if retry_after_str and retry_after_str.isdigit():
                            wait_time = int(retry_after_str)
                        logger.warning(
                            f"Rate limited by Slack on conversations.history for channel {channel_id}. "
                            f"Retrying after {wait_time} seconds. Cursor: {next_cursor}"
                        )
                        time.sleep(wait_time)
                        # current_api_call_successful remains False, loop will retry this page
                    else:
                        raise # Re-raise to outer handler for not_in_channel or other SlackApiErrors
                
                if not current_api_call_successful:
                    continue # Retry the current page fetch due to handled rate limit

                # Process result if successful
                batch = result["messages"]
                messages.extend(batch)
                
                if result.get("has_more", False) and len(messages) < limit:
                    next_cursor = result["response_metadata"]["next_cursor"]
                else:
                    break # Exit pagination loop
            
            except SlackApiError as e: # Outer catch for not_in_channel or unhandled SlackApiErrors from inner try
                if (e.response is not None and 
                    hasattr(e.response, 'data') and
                    isinstance(e.response.data, dict) and
                    e.response.data.get('error') == 'not_in_channel'):
                    logger.warning(
                        f"Bot is not in channel '{channel_id}'. Cannot fetch history. "
                        "Please add the bot to this channel."
                    )
                    return [] 
                # For other SlackApiErrors from inner block or this level
                raise SlackApiError(f"Error retrieving history for channel {channel_id}: {e}", e.response)
            except Exception as general_error: # Catch any other unexpected errors
                logger.error(f"Unexpected error in get_conversation_history for channel {channel_id}: {general_error}")
                # Re-raise the general error to allow higher-level handling or visibility
                raise 
        
        return messages[:limit]

    @staticmethod
    def convert_date_to_timestamp(date_str: str) -> Optional[int]:
        """
        Convert a date string in format YYYY-MM-DD to Unix timestamp.
        
        Args:
            date_str: Date string in YYYY-MM-DD format
        
        Returns:
            Unix timestamp (seconds since epoch) or None if invalid format
        """
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return int(dt.timestamp())
        except ValueError:
            return None
    
    def get_history_by_date_range(
        self, 
        channel_id: str, 
        start_date: str, 
        end_date: str, 
        limit: int = 1000
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Fetch conversation history within a date range.
        
        Args:
            channel_id: The ID of the channel to fetch history for
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format (inclusive)
            limit: Maximum number of messages to return
        
        Returns:
            Tuple containing (messages list, error message or None)
        """
        oldest = self.convert_date_to_timestamp(start_date)
        if not oldest:
            return [], f"Invalid start date format: {start_date}. Please use YYYY-MM-DD."
        
        latest = self.convert_date_to_timestamp(end_date)
        if not latest:
            return [], f"Invalid end date format: {end_date}. Please use YYYY-MM-DD."
        
        # Add one day to end date to make it inclusive
        latest += 86400  # seconds in a day
        
        try:
            messages = self.get_conversation_history(
                channel_id=channel_id,
                limit=limit,
                oldest=oldest,
                latest=latest
            )
            return messages, None
        except SlackApiError as e:
            return [], f"Slack API error: {str(e)}"
        except ValueError as e:
            return [], str(e)
    
    def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """
        Get information about a user.
        
        Args:
            user_id: The ID of the user to get info for
            
        Returns:
            User information dictionary
            
        Raises:
            ValueError: If no Slack client has been initialized
            SlackApiError: If there's an error calling the Slack API
        """
        if not self.client:
            raise ValueError("Slack client not initialized. Call set_token() first.")
        
        while True:
            try:
                # Proactive delay for users.info (Tier 4) - generally not needed unless called extremely rapidly.
                # For now, we are only adding Retry-After as per plan.
                # time.sleep(0.6) # Optional: ~100 req/min if ever needed.

                result = self.client.users_info(user=user_id)
                return result["user"] # Success, return and exit loop implicitly

            except SlackApiError as e_user_info:
                if e_user_info.response is not None and e_user_info.response.status_code == 429:
                    retry_after_str = e_user_info.response.headers.get('Retry-After')
                    wait_time = 30  # Default for Tier 4, can be adjusted
                    if retry_after_str and retry_after_str.isdigit():
                        wait_time = int(retry_after_str)
                    logger.warning(f"Rate limited by Slack on users.info for user {user_id}. Retrying after {wait_time} seconds.")
                    time.sleep(wait_time)
                    continue  # Retry the API call
                else:
                    # Not a 429 error, or no response object, re-raise
                    raise SlackApiError(f"Error retrieving user info for {user_id}: {e_user_info}", e_user_info.response)
            except Exception as general_error: # Catch any other unexpected errors
                logger.error(f"Unexpected error in get_user_info for user {user_id}: {general_error}")
                raise # Re-raise unexpected errors
    
    def format_message(self, msg: Dict[str, Any], include_user_info: bool = False) -> Dict[str, Any]:
        """
        Format a message for easier consumption.
        
        Args:
            msg: The message object from Slack API
            include_user_info: Whether to fetch and include user info
            
        Returns:
            Formatted message dictionary
        """
        formatted = {
            "text": msg.get("text", ""),
            "timestamp": msg.get("ts"),
            "datetime": datetime.fromtimestamp(float(msg.get("ts", 0))).strftime('%Y-%m-%d %H:%M:%S'),
            "user_id": msg.get("user", "UNKNOWN"),
            "has_attachments": bool(msg.get("attachments")),
            "has_files": bool(msg.get("files")),
            "thread_ts": msg.get("thread_ts"),
            "is_thread": "thread_ts" in msg,
        }
        
        if include_user_info and "user" in msg and self.client:
            try:
                user_info = self.get_user_info(msg["user"])
                formatted["user_name"] = user_info.get("real_name", "Unknown")
                formatted["user_email"] = user_info.get("profile", {}).get("email", "")
            except Exception:
                # If we can't get user info, just continue without it
                formatted["user_name"] = "Unknown"
                
        return formatted


# Example usage (uncomment to use):
"""
if __name__ == "__main__":
    # Set your token here or via environment variable
    token = os.environ.get("SLACK_API_TOKEN", "xoxb-your-token-here")
    
    slack = SlackHistory(token)
    
    # Get all channels
    try:
        channels = slack.get_all_channels()
        print("Available channels:")
        for name, channel_id in sorted(channels.items()):
            print(f"- {name}: {channel_id}")
        
        # Example: Get history for a specific channel and date range
        channel_id = channels.get("general")
        if channel_id:
            messages, error = slack.get_history_by_date_range(
                channel_id=channel_id,
                start_date="2023-01-01",
                end_date="2023-01-31",
                limit=500
            )
            
            if error:
                print(f"Error: {error}")
            else:
                print(f"\nRetrieved {len(messages)} messages from #general")
                
                # Print formatted messages
                for msg in messages[:10]:  # Show first 10 messages
                    formatted = slack.format_message(msg, include_user_info=True)
                    print(f"[{formatted['datetime']}] {formatted['user_name']}: {formatted['text']}")
    
    except Exception as e:
        print(f"Error: {e}")
"""