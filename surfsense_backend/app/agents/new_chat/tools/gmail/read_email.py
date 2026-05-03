import logging
from typing import Any

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import SearchSourceConnector, SearchSourceConnectorType

logger = logging.getLogger(__name__)

_GMAIL_TYPES = [
    SearchSourceConnectorType.GOOGLE_GMAIL_CONNECTOR,
    SearchSourceConnectorType.COMPOSIO_GMAIL_CONNECTOR,
]


def create_read_gmail_email_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
):
    @tool
    async def read_gmail_email(message_id: str) -> dict[str, Any]:
        """Read the full content of a specific Gmail email by its message ID.

        Use after search_gmail to get the complete body of an email.

        Args:
            message_id: The Gmail message ID (from search_gmail results).

        Returns:
            Dictionary with status and the full email content formatted as markdown.
        """
        if db_session is None or search_space_id is None or user_id is None:
            return {"status": "error", "message": "Gmail tool not properly configured."}

        try:
            result = await db_session.execute(
                select(SearchSourceConnector).filter(
                    SearchSourceConnector.search_space_id == search_space_id,
                    SearchSourceConnector.user_id == user_id,
                    SearchSourceConnector.connector_type.in_(_GMAIL_TYPES),
                )
            )
            connector = result.scalars().first()
            if not connector:
                return {
                    "status": "error",
                    "message": "No Gmail connector found. Please connect Gmail in your workspace settings.",
                }

            if (
                connector.connector_type
                == SearchSourceConnectorType.COMPOSIO_GMAIL_CONNECTOR
            ):
                cca_id = connector.config.get("composio_connected_account_id")
                if not cca_id:
                    return {
                        "status": "error",
                        "message": "Composio connected account ID not found.",
                    }

                from app.agents.new_chat.tools.gmail.search_emails import (
                    _format_gmail_summary,
                )
                from app.services.composio_service import ComposioService

                service = ComposioService()
                detail, error = await service.get_gmail_message_detail(
                    connected_account_id=cca_id,
                    entity_id=f"surfsense_{user_id}",
                    message_id=message_id,
                )
                if error:
                    return {"status": "error", "message": error}
                if not detail:
                    return {
                        "status": "not_found",
                        "message": f"Email with ID '{message_id}' not found.",
                    }

                summary = _format_gmail_summary(detail)
                content = (
                    f"# {summary['subject']}\n\n"
                    f"**From:** {summary['from']}\n"
                    f"**To:** {summary['to']}\n"
                    f"**Date:** {summary['date']}\n\n"
                    f"## Message Content\n\n"
                    f"{detail.get('messageText') or detail.get('snippet') or ''}\n\n"
                    f"## Message Details\n\n"
                    f"- **Message ID:** {summary['message_id']}\n"
                    f"- **Thread ID:** {summary['thread_id']}\n"
                )
                return {
                    "status": "success",
                    "message_id": summary["message_id"] or message_id,
                    "content": content,
                }

            from app.agents.new_chat.tools.gmail.search_emails import _build_credentials

            creds = _build_credentials(connector)

            from app.connectors.google_gmail_connector import GoogleGmailConnector

            gmail = GoogleGmailConnector(
                credentials=creds,
                session=db_session,
                user_id=user_id,
                connector_id=connector.id,
            )

            detail, error = await gmail.get_message_details(message_id)
            if error:
                if (
                    "re-authenticate" in error.lower()
                    or "authentication failed" in error.lower()
                ):
                    return {
                        "status": "auth_error",
                        "message": error,
                        "connector_type": "gmail",
                    }
                return {"status": "error", "message": error}

            if not detail:
                return {
                    "status": "not_found",
                    "message": f"Email with ID '{message_id}' not found.",
                }

            content = gmail.format_message_to_markdown(detail)

            return {"status": "success", "message_id": message_id, "content": content}

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise
            logger.error("Error reading Gmail email: %s", e, exc_info=True)
            return {
                "status": "error",
                "message": "Failed to read email. Please try again.",
            }

    return read_gmail_email
