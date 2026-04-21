import logging
from datetime import datetime
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


def _build_credentials(connector: SearchSourceConnector):
    """Build Google OAuth Credentials from a Gmail connector's config."""
    if connector.connector_type == SearchSourceConnectorType.COMPOSIO_GMAIL_CONNECTOR:
        from app.utils.google_credentials import build_composio_credentials

        cca_id = connector.config.get("composio_connected_account_id")
        if not cca_id:
            raise ValueError("Composio connected account ID not found.")
        return build_composio_credentials(cca_id)

    from google.oauth2.credentials import Credentials

    from app.config import config
    from app.utils.oauth_security import TokenEncryption

    cfg = dict(connector.config)
    if cfg.get("_token_encrypted") and config.SECRET_KEY:
        enc = TokenEncryption(config.SECRET_KEY)
        for key in ("token", "refresh_token", "client_secret"):
            if cfg.get(key):
                cfg[key] = enc.decrypt_token(cfg[key])

    exp = (cfg.get("expiry") or "").replace("Z", "")
    return Credentials(
        token=cfg.get("token"),
        refresh_token=cfg.get("refresh_token"),
        token_uri=cfg.get("token_uri"),
        client_id=cfg.get("client_id"),
        client_secret=cfg.get("client_secret"),
        scopes=cfg.get("scopes", []),
        expiry=datetime.fromisoformat(exp) if exp else None,
    )


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
                if "re-authenticate" in error.lower() or "authentication failed" in error.lower():
                    return {"status": "auth_error", "message": error, "connector_type": "gmail"}
                return {"status": "error", "message": error}

            if not messages_list:
                return {"status": "success", "emails": [], "total": 0, "message": "No emails found."}

            emails = []
            for msg in messages_list:
                detail, err = await gmail.get_message_details(msg["id"])
                if err:
                    continue
                headers = {
                    h["name"].lower(): h["value"]
                    for h in detail.get("payload", {}).get("headers", [])
                }
                emails.append({
                    "message_id": detail.get("id"),
                    "thread_id": detail.get("threadId"),
                    "subject": headers.get("subject", "No Subject"),
                    "from": headers.get("from", "Unknown"),
                    "to": headers.get("to", ""),
                    "date": headers.get("date", ""),
                    "snippet": detail.get("snippet", ""),
                    "labels": detail.get("labelIds", []),
                })

            return {"status": "success", "emails": emails, "total": len(emails)}

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise
            logger.error("Error searching Gmail: %s", e, exc_info=True)
            return {"status": "error", "message": "Failed to search Gmail. Please try again."}

    return search_gmail
