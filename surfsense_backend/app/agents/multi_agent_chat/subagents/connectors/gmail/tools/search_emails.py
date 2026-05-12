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


def create_search_gmail_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
):
    @tool
    async def search_gmail(
        query: str,
        max_results: int = 10,
    ) -> dict[str, Any]:
        """Search emails in the user's Gmail inbox using Gmail search syntax.

        Args:
            query: Gmail search query, same syntax as the Gmail search bar.
                Examples: "from:alice@example.com", "subject:meeting",
                "is:unread", "after:2024/01/01 before:2024/02/01",
                "has:attachment", "in:sent".
            max_results: Number of emails to return (default 10, max 20).

        Returns:
            Dictionary with status and a list of email summaries including
            message_id, subject, from, date, snippet.
        """
        if db_session is None or search_space_id is None or user_id is None:
            return {"status": "error", "message": "Gmail tool not properly configured."}

        max_results = min(max_results, 20)

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
                        "message": "Composio connected account ID not found for this Gmail connector.",
                    }

                from app.agents.new_chat.tools.gmail.search_emails import (
                    _format_gmail_summary,
                )
                from app.services.composio_service import ComposioService

                (
                    messages,
                    _next,
                    _estimate,
                    error,
                ) = await ComposioService().get_gmail_messages(
                    connected_account_id=cca_id,
                    entity_id=f"surfsense_{user_id}",
                    query=query,
                    max_results=max_results,
                )
                if error:
                    return {"status": "error", "message": error}

                emails = [_format_gmail_summary(m) for m in messages]
                if not emails:
                    return {
                        "status": "success",
                        "emails": [],
                        "total": 0,
                        "message": "No emails found.",
                    }
                return {"status": "success", "emails": emails, "total": len(emails)}

            from app.agents.new_chat.tools.gmail.search_emails import (
                _build_credentials,
            )

            creds = _build_credentials(connector)

            from app.connectors.google_gmail_connector import GoogleGmailConnector

            gmail = GoogleGmailConnector(
                credentials=creds,
                session=db_session,
                user_id=user_id,
                connector_id=connector.id,
            )

            messages_list, error = await gmail.get_messages_list(
                max_results=max_results, query=query
            )
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

            if not messages_list:
                return {
                    "status": "success",
                    "emails": [],
                    "total": 0,
                    "message": "No emails found.",
                }

            emails = []
            for msg in messages_list:
                detail, err = await gmail.get_message_details(msg["id"])
                if err:
                    continue
                headers = {
                    h["name"].lower(): h["value"]
                    for h in detail.get("payload", {}).get("headers", [])
                }
                emails.append(
                    {
                        "message_id": detail.get("id"),
                        "thread_id": detail.get("threadId"),
                        "subject": headers.get("subject", "No Subject"),
                        "from": headers.get("from", "Unknown"),
                        "to": headers.get("to", ""),
                        "date": headers.get("date", ""),
                        "snippet": detail.get("snippet", ""),
                        "labels": detail.get("labelIds", []),
                    }
                )

            return {"status": "success", "emails": emails, "total": len(emails)}

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise
            logger.error("Error searching Gmail: %s", e, exc_info=True)
            return {
                "status": "error",
                "message": "Failed to search Gmail. Please try again.",
            }

    return search_gmail
