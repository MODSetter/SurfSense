"""
Composio Connector Module.

Provides a unified interface for interacting with various services via Composio,
primarily used during indexing operations.
"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import SearchSourceConnector
from app.services.composio_service import INDEXABLE_TOOLKITS, ComposioService

logger = logging.getLogger(__name__)


class ComposioConnector:
    """
    Generic Composio connector for data retrieval.

    Wraps the ComposioService to provide toolkit-specific data access
    for indexing operations.
    """

    def __init__(
        self,
        session: AsyncSession,
        connector_id: int,
    ):
        """
        Initialize the Composio connector.

        Args:
            session: Database session for updating connector.
            connector_id: ID of the SearchSourceConnector.
        """
        self._session = session
        self._connector_id = connector_id
        self._service: ComposioService | None = None
        self._connector: SearchSourceConnector | None = None
        self._config: dict[str, Any] | None = None

    async def _load_connector(self) -> SearchSourceConnector:
        """Load connector from database."""
        if self._connector is None:
            result = await self._session.execute(
                select(SearchSourceConnector).filter(
                    SearchSourceConnector.id == self._connector_id
                )
            )
            self._connector = result.scalars().first()
            if not self._connector:
                raise ValueError(f"Connector {self._connector_id} not found")
            self._config = self._connector.config or {}
        return self._connector

    async def _get_service(self) -> ComposioService:
        """Get or create the Composio service instance."""
        if self._service is None:
            self._service = ComposioService()
        return self._service

    async def get_config(self) -> dict[str, Any]:
        """Get the connector configuration."""
        await self._load_connector()
        return self._config or {}

    async def get_toolkit_id(self) -> str:
        """Get the toolkit ID for this connector."""
        config = await self.get_config()
        return config.get("toolkit_id", "")

    async def get_connected_account_id(self) -> str | None:
        """Get the Composio connected account ID."""
        config = await self.get_config()
        return config.get("composio_connected_account_id")

    async def get_entity_id(self) -> str:
        """Get the Composio entity ID (user identifier)."""
        await self._load_connector()
        # Entity ID is constructed from the connector's user_id
        return f"surfsense_{self._connector.user_id}"

    async def is_indexable(self) -> bool:
        """Check if this connector's toolkit supports indexing."""
        toolkit_id = await self.get_toolkit_id()
        return toolkit_id in INDEXABLE_TOOLKITS

    # ===== Google Drive Methods =====

    async def list_drive_files(
        self,
        folder_id: str | None = None,
        page_token: str | None = None,
        page_size: int = 100,
    ) -> tuple[list[dict[str, Any]], str | None, str | None]:
        """
        List files from Google Drive via Composio.

        Args:
            folder_id: Optional folder ID to list contents of.
            page_token: Pagination token.
            page_size: Number of files per page.

        Returns:
            Tuple of (files list, next_page_token, error message).
        """
        connected_account_id = await self.get_connected_account_id()
        if not connected_account_id:
            return [], None, "No connected account ID found"

        entity_id = await self.get_entity_id()
        service = await self._get_service()
        return await service.get_drive_files(
            connected_account_id=connected_account_id,
            entity_id=entity_id,
            folder_id=folder_id,
            page_token=page_token,
            page_size=page_size,
        )

    async def get_drive_file_content(
        self, file_id: str
    ) -> tuple[bytes | None, str | None]:
        """
        Download file content from Google Drive via Composio.

        Args:
            file_id: Google Drive file ID.

        Returns:
            Tuple of (file content bytes, error message).
        """
        connected_account_id = await self.get_connected_account_id()
        if not connected_account_id:
            return None, "No connected account ID found"

        entity_id = await self.get_entity_id()
        service = await self._get_service()
        return await service.get_drive_file_content(
            connected_account_id=connected_account_id,
            entity_id=entity_id,
            file_id=file_id,
        )

    # ===== Gmail Methods =====

    async def list_gmail_messages(
        self,
        query: str = "",
        max_results: int = 100,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        List Gmail messages via Composio.

        Args:
            query: Gmail search query.
            max_results: Maximum number of messages.

        Returns:
            Tuple of (messages list, error message).
        """
        connected_account_id = await self.get_connected_account_id()
        if not connected_account_id:
            return [], "No connected account ID found"

        entity_id = await self.get_entity_id()
        service = await self._get_service()
        return await service.get_gmail_messages(
            connected_account_id=connected_account_id,
            entity_id=entity_id,
            query=query,
            max_results=max_results,
        )

    async def get_gmail_message_detail(
        self, message_id: str
    ) -> tuple[dict[str, Any] | None, str | None]:
        """
        Get full details of a Gmail message via Composio.

        Args:
            message_id: Gmail message ID.

        Returns:
            Tuple of (message details, error message).
        """
        connected_account_id = await self.get_connected_account_id()
        if not connected_account_id:
            return None, "No connected account ID found"

        entity_id = await self.get_entity_id()
        service = await self._get_service()
        return await service.get_gmail_message_detail(
            connected_account_id=connected_account_id,
            entity_id=entity_id,
            message_id=message_id,
        )

    # ===== Google Calendar Methods =====

    async def list_calendar_events(
        self,
        time_min: str | None = None,
        time_max: str | None = None,
        max_results: int = 250,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        List Google Calendar events via Composio.

        Args:
            time_min: Start time (RFC3339 format).
            time_max: End time (RFC3339 format).
            max_results: Maximum number of events.

        Returns:
            Tuple of (events list, error message).
        """
        connected_account_id = await self.get_connected_account_id()
        if not connected_account_id:
            return [], "No connected account ID found"

        entity_id = await self.get_entity_id()
        service = await self._get_service()
        return await service.get_calendar_events(
            connected_account_id=connected_account_id,
            entity_id=entity_id,
            time_min=time_min,
            time_max=time_max,
            max_results=max_results,
        )

    # ===== Utility Methods =====

    def format_gmail_message_to_markdown(self, message: dict[str, Any]) -> str:
        """
        Format a Gmail message to markdown.

        Args:
            message: Message object from Composio's GMAIL_FETCH_EMAILS response.
                    Composio structure: messageId, messageText, messageTimestamp,
                    payload.headers, labelIds, attachmentList

        Returns:
            Formatted markdown string.
        """
        try:
            # Composio uses 'messageId' (camelCase)
            message_id = message.get("messageId", "") or message.get("id", "")
            label_ids = message.get("labelIds", [])

            # Extract headers from payload
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
            # Composio provides messageTimestamp directly
            date_str = message.get("messageTimestamp", "") or header_dict.get(
                "date", "Unknown Date"
            )

            # Build markdown content
            markdown_content = f"# {subject}\n\n"
            markdown_content += f"**From:** {from_email}\n"
            markdown_content += f"**To:** {to_email}\n"
            markdown_content += f"**Date:** {date_str}\n"

            if label_ids:
                markdown_content += f"**Labels:** {', '.join(label_ids)}\n"

            markdown_content += "\n---\n\n"

            # Composio provides full message text in 'messageText'
            message_text = message.get("messageText", "")
            if message_text:
                markdown_content += f"## Content\n\n{message_text}\n\n"
            else:
                # Fallback to snippet if no messageText
                snippet = message.get("snippet", "")
                if snippet:
                    markdown_content += f"## Preview\n\n{snippet}\n\n"

            # Add attachment info if present
            attachments = message.get("attachmentList", [])
            if attachments:
                markdown_content += "## Attachments\n\n"
                for att in attachments:
                    att_name = att.get("filename", att.get("name", "Unknown"))
                    markdown_content += f"- {att_name}\n"
                markdown_content += "\n"

            # Add message metadata
            markdown_content += "## Message Details\n\n"
            markdown_content += f"- **Message ID:** {message_id}\n"

            return markdown_content

        except Exception as e:
            return f"Error formatting message to markdown: {e!s}"

    def format_calendar_event_to_markdown(self, event: dict[str, Any]) -> str:
        """
        Format a Google Calendar event to markdown.

        Args:
            event: Event object from Google Calendar API.

        Returns:
            Formatted markdown string.
        """
        from datetime import datetime

        try:
            # Extract basic event information
            summary = event.get("summary", "No Title")
            description = event.get("description", "")
            location = event.get("location", "")

            # Extract start and end times
            start = event.get("start", {})
            end = event.get("end", {})

            start_time = start.get("dateTime") or start.get("date", "")
            end_time = end.get("dateTime") or end.get("date", "")

            # Format times for display
            def format_time(time_str: str) -> str:
                if not time_str:
                    return "Unknown"
                try:
                    if "T" in time_str:
                        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                        return dt.strftime("%Y-%m-%d %H:%M")
                    return time_str
                except Exception:
                    return time_str

            start_formatted = format_time(start_time)
            end_formatted = format_time(end_time)

            # Extract attendees
            attendees = event.get("attendees", [])
            attendee_list = []
            for attendee in attendees:
                email = attendee.get("email", "")
                display_name = attendee.get("displayName", email)
                response_status = attendee.get("responseStatus", "")
                attendee_list.append(f"- {display_name} ({response_status})")

            # Build markdown content
            markdown_content = f"# {summary}\n\n"
            markdown_content += f"**Start:** {start_formatted}\n"
            markdown_content += f"**End:** {end_formatted}\n"

            if location:
                markdown_content += f"**Location:** {location}\n"

            markdown_content += "\n"

            if description:
                markdown_content += f"## Description\n\n{description}\n\n"

            if attendee_list:
                markdown_content += "## Attendees\n\n"
                markdown_content += "\n".join(attendee_list)
                markdown_content += "\n\n"

            # Add event metadata
            markdown_content += "## Event Details\n\n"
            markdown_content += f"- **Event ID:** {event.get('id', 'Unknown')}\n"
            markdown_content += f"- **Created:** {event.get('created', 'Unknown')}\n"
            markdown_content += f"- **Updated:** {event.get('updated', 'Unknown')}\n"

            return markdown_content

        except Exception as e:
            return f"Error formatting event to markdown: {e!s}"
