"""
Google Gmail Connector Module | Google OAuth Credentials | Gmail API
A module for retrieving emails from Gmail using Google OAuth credentials.
Allows fetching emails from Gmail mailbox using Google OAuth credentials.
"""

import base64
import json
import re
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm.attributes import flag_modified

from app.db import (
    SearchSourceConnector,
    SearchSourceConnectorType,
)


class GoogleGmailConnector:
    """Class for retrieving emails from Gmail using Google OAuth credentials."""

    def __init__(
        self,
        credentials: Credentials,
        session: AsyncSession,
        user_id: str,
        connector_id: int | None = None,
    ):
        """
        Initialize the GoogleGmailConnector class.
        Args:
            credentials: Google OAuth Credentials object
            session: Database session for updating connector
            user_id: User ID (kept for backward compatibility)
            connector_id: Optional connector ID for direct updates
        """
        self._credentials = credentials
        self._session = session
        self._user_id = user_id
        self._connector_id = connector_id
        self.service = None

    async def _get_credentials(
        self,
    ) -> Credentials:
        """
        Get valid Google OAuth credentials.
        Returns:
            Google OAuth credentials
        Raises:
            ValueError: If credentials have not been set
            Exception: If credential refresh fails
        """
        if not all(
            [
                self._credentials.client_id,
                self._credentials.client_secret,
                self._credentials.refresh_token,
            ]
        ):
            raise ValueError(
                "Google OAuth credentials (client_id, client_secret, refresh_token) must be set"
            )

        if self._credentials and not self._credentials.expired:
            return self._credentials

        # Create credentials from refresh token
        self._credentials = Credentials(
            token=self._credentials.token,
            refresh_token=self._credentials.refresh_token,
            token_uri=self._credentials.token_uri,
            client_id=self._credentials.client_id,
            client_secret=self._credentials.client_secret,
            scopes=self._credentials.scopes,
            expiry=self._credentials.expiry,
        )

        # Refresh the token if needed
        if self._credentials.expired or not self._credentials.valid:
            try:
                self._credentials.refresh(Request())
                # Update the connector config in DB
                if self._session:
                    # Use connector_id if available, otherwise fall back to user_id query
                    if self._connector_id:
                        result = await self._session.execute(
                            select(SearchSourceConnector).filter(
                                SearchSourceConnector.id == self._connector_id
                            )
                        )
                    else:
                        result = await self._session.execute(
                            select(SearchSourceConnector).filter(
                                SearchSourceConnector.user_id == self._user_id,
                                SearchSourceConnector.connector_type
                                == SearchSourceConnectorType.GOOGLE_GMAIL_CONNECTOR,
                            )
                        )
                    connector = result.scalars().first()
                    if connector is None:
                        raise RuntimeError(
                            "GMAIL connector not found; cannot persist refreshed token."
                        )
                    connector.config = json.loads(self._credentials.to_json())
                    flag_modified(connector, "config")
                    await self._session.commit()
            except Exception as e:
                raise Exception(
                    f"Failed to refresh Google OAuth credentials: {e!s}"
                ) from e

        return self._credentials

    async def _get_service(self):
        """
        Get the Gmail service instance using Google OAuth credentials.
        Returns:
            Gmail service instance
        Raises:
            ValueError: If credentials have not been set
            Exception: If service creation fails
        """
        if self.service:
            return self.service

        try:
            credentials = await self._get_credentials()
            self.service = build("gmail", "v1", credentials=credentials)
            return self.service
        except Exception as e:
            raise Exception(f"Failed to create Gmail service: {e!s}") from e

    async def get_user_profile(self) -> tuple[dict[str, Any], str | None]:
        """
        Fetch user's Gmail profile information.
        Returns:
            Tuple containing (profile dict, error message or None)
        """
        try:
            service = await self._get_service()
            profile = service.users().getProfile(userId="me").execute()

            return {
                "email_address": profile.get("emailAddress"),
                "messages_total": profile.get("messagesTotal", 0),
                "threads_total": profile.get("threadsTotal", 0),
                "history_id": profile.get("historyId"),
            }, None

        except Exception as e:
            return {}, f"Error fetching user profile: {e!s}"

    async def get_messages_list(
        self,
        max_results: int = 100,
        query: str = "",
        label_ids: list[str] | None = None,
        include_spam_trash: bool = False,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Fetch list of messages from Gmail.
        Args:
            max_results: Maximum number of messages to fetch (default: 100)
            query: Gmail search query (e.g., "is:unread", "from:example@gmail.com")
            label_ids: List of label IDs to filter by
            include_spam_trash: Whether to include spam and trash
        Returns:
            Tuple containing (messages list, error message or None)
        """
        try:
            service = await self._get_service()

            # Build request parameters
            request_params = {
                "userId": "me",
                "maxResults": max_results,
                "includeSpamTrash": include_spam_trash,
            }

            if query:
                request_params["q"] = query
            if label_ids:
                request_params["labelIds"] = label_ids

            # Get messages list
            result = service.users().messages().list(**request_params).execute()
            messages = result.get("messages", [])

            return messages, None

        except Exception as e:
            return [], f"Error fetching messages list: {e!s}"

    async def get_message_details(
        self, message_id: str
    ) -> tuple[dict[str, Any], str | None]:
        """
        Fetch detailed information for a specific message.
        Args:
            message_id: The ID of the message to fetch
        Returns:
            Tuple containing (message details dict, error message or None)
        """
        try:
            service = await self._get_service()

            # Get full message details
            message = (
                service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )

            return message, None

        except Exception as e:
            return {}, f"Error fetching message details: {e!s}"

    async def get_recent_messages(
        self,
        max_results: int = 50,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Fetch recent messages from Gmail within specified date range.
        Args:
            max_results: Maximum number of messages to fetch (default: 50)
            start_date: Start date in YYYY-MM-DD format (default: 30 days ago)
            end_date: End date in YYYY-MM-DD format (default: today)
        Returns:
            Tuple containing (messages list with details, error message or None)
        """
        try:
            from datetime import datetime, timedelta

            # Build date query
            query_parts = []

            if start_date:
                # Parse start_date from YYYY-MM-DD to Gmail query format YYYY/MM/DD
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                start_query = start_dt.strftime("%Y/%m/%d")
                query_parts.append(f"after:{start_query}")
            else:
                # Default to 30 days ago
                cutoff_date = datetime.now() - timedelta(days=30)
                date_query = cutoff_date.strftime("%Y/%m/%d")
                query_parts.append(f"after:{date_query}")

            if end_date:
                # Parse end_date from YYYY-MM-DD to Gmail query format YYYY/MM/DD
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                end_query = end_dt.strftime("%Y/%m/%d")
                query_parts.append(f"before:{end_query}")

            query = " ".join(query_parts)

            # Get messages list
            messages_list, error = await self.get_messages_list(
                max_results=max_results, query=query
            )

            if error:
                return [], error

            # Get detailed information for each message
            detailed_messages = []
            for msg in messages_list:
                message_details, detail_error = await self.get_message_details(
                    msg["id"]
                )
                if detail_error:
                    continue  # Skip messages that can't be fetched
                detailed_messages.append(message_details)

            return detailed_messages, None

        except Exception as e:
            return [], f"Error fetching recent messages: {e!s}"

    def extract_message_text(self, message: dict[str, Any]) -> str:
        """
        Extract text content from a Gmail message.
        Args:
            message: Gmail message object
        Returns:
            Extracted text content
        """

        def get_message_parts(payload):
            """Recursively extract message parts."""
            parts = []

            if "parts" in payload:
                for part in payload["parts"]:
                    parts.extend(get_message_parts(part))
            else:
                parts.append(payload)

            return parts

        try:
            payload = message.get("payload", {})
            parts = get_message_parts(payload)

            text_content = ""

            for part in parts:
                mime_type = part.get("mimeType", "")
                body = part.get("body", {})
                data = body.get("data", "")

                if mime_type == "text/plain" and data:
                    # Decode base64 content
                    decoded_data = base64.urlsafe_b64decode(data + "===").decode(
                        "utf-8", errors="ignore"
                    )
                    text_content += decoded_data + "\n"
                elif mime_type == "text/html" and data and not text_content:
                    # Use HTML as fallback if no plain text
                    decoded_data = base64.urlsafe_b64decode(data + "===").decode(
                        "utf-8", errors="ignore"
                    )
                    # Basic HTML tag removal (you might want to use a proper HTML parser)

                    text_content = re.sub(r"<[^>]+>", "", decoded_data)

            return text_content.strip()

        except Exception as e:
            return f"Error extracting message text: {e!s}"

    def format_message_to_markdown(self, message: dict[str, Any]) -> str:
        """
        Format a Gmail message to markdown.
        Args:
            message: Message object from Gmail API
        Returns:
            Formatted markdown string
        """
        try:
            # Extract basic message information
            message_id = message.get("id", "")
            thread_id = message.get("threadId", "")
            label_ids = message.get("labelIds", [])

            # Extract headers
            payload = message.get("payload", {})
            headers = payload.get("headers", [])

            # Parse headers into a dict
            header_dict = {}
            for header in headers:
                name = header.get("name", "").lower()
                value = header.get("value", "")
                header_dict[name] = value

            # Extract key information
            subject = header_dict.get("subject", "No Subject")
            from_email = header_dict.get("from", "Unknown Sender")
            to_email = header_dict.get("to", "Unknown Recipient")
            date_str = header_dict.get("date", "Unknown Date")

            # Extract message content
            message_text = self.extract_message_text(message)

            # Build markdown content
            markdown_content = f"# {subject}\n\n"

            # Add message details
            markdown_content += f"**From:** {from_email}\n"
            markdown_content += f"**To:** {to_email}\n"
            markdown_content += f"**Date:** {date_str}\n"

            if label_ids:
                markdown_content += f"**Labels:** {', '.join(label_ids)}\n"

            markdown_content += "\n"

            # Add message content
            if message_text:
                markdown_content += f"## Message Content\n\n{message_text}\n\n"

            # Add message metadata
            markdown_content += "## Message Details\n\n"
            markdown_content += f"- **Message ID:** {message_id}\n"
            markdown_content += f"- **Thread ID:** {thread_id}\n"

            # Add snippet if available
            snippet = message.get("snippet", "")
            if snippet:
                markdown_content += f"- **Snippet:** {snippet}\n"

            return markdown_content

        except Exception as e:
            return f"Error formatting message to markdown: {e!s}"
