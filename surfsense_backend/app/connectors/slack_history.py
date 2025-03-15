"""
Slack History Module

A module for retrieving conversation history from Slack channels.
Allows fetching channel lists and message history with date range filtering.
"""

import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union


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
    
    def get_all_channels(self, include_private: bool = True) -> Dict[str, str]:
        """
        Fetch all channels that the bot has access to.
        
        Args:
            include_private: Whether to include private channels
        
        Returns:
            Dictionary mapping channel names to channel IDs
        
        Raises:
            ValueError: If no Slack client has been initialized
            SlackApiError: If there's an error calling the Slack API
        """
        if not self.client:
            raise ValueError("Slack client not initialized. Call set_token() first.")
        
        channels_dict = {}
        types = "public_channel"
        if include_private:
            types += ",private_channel"
        
        try:
            # Call the conversations.list method
            result = self.client.conversations_list(
                types=types,
                limit=1000  # Maximum allowed by API
            )
            channels = result["channels"]
            
            # Handle pagination for workspaces with many channels
            while result.get("response_metadata", {}).get("next_cursor"):
                next_cursor = result["response_metadata"]["next_cursor"]
                
                # Get the next batch of channels
                result = self.client.conversations_list(
                    types=types,
                    cursor=next_cursor,
                    limit=1000
                )
                channels.extend(result["channels"])
            
            # Create a dictionary mapping channel names to IDs
            for channel in channels:
                channels_dict[channel["name"]] = channel["id"]
            
            return channels_dict
        
        except SlackApiError as e:
            raise SlackApiError(f"Error retrieving channels: {e}", e.response)
    
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
        
        try:
            # Call the conversations.history method
            messages = []
            next_cursor = None
            
            while True:
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
                
                result = self.client.conversations_history(**kwargs)
                batch = result["messages"]
                messages.extend(batch)
                
                # Check if we need to paginate
                if result.get("has_more", False) and len(messages) < limit:
                    next_cursor = result["response_metadata"]["next_cursor"]
                else:
                    break
            
            # Respect the overall limit parameter
            return messages[:limit]
        
        except SlackApiError as e:
            raise SlackApiError(f"Error retrieving history for channel {channel_id}: {e}", e.response)
    
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
            
        try:
            result = self.client.users_info(user=user_id)
            return result["user"]
        except SlackApiError as e:
            raise SlackApiError(f"Error retrieving user info for {user_id}: {e}", e.response)
    
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