import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from sqlalchemy import String, and_, cast, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm.attributes import flag_modified

from app.db import (
    Document,
    DocumentType,
    SearchSourceConnector,
    SearchSourceConnectorType,
)
from app.utils.google_credentials import build_composio_credentials

logger = logging.getLogger(__name__)


@dataclass
class GmailAccount:
    id: int
    name: str
    email: str

    @classmethod
    def from_connector(cls, connector: SearchSourceConnector) -> "GmailAccount":
        email = ""
        if connector.name and " - " in connector.name:
            email = connector.name.split(" - ", 1)[1]
        return cls(id=connector.id, name=connector.name, email=email)

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "email": self.email}


@dataclass
class GmailMessage:
    message_id: str
    thread_id: str
    subject: str
    sender: str
    date: str
    connector_id: int
    document_id: int

    @classmethod
    def from_document(cls, document: Document) -> "GmailMessage":
        meta = document.document_metadata or {}
        return cls(
            message_id=meta.get("message_id", ""),
            thread_id=meta.get("thread_id", ""),
            subject=meta.get("subject", document.title),
            sender=meta.get("sender", ""),
            date=meta.get("date", ""),
            connector_id=document.connector_id,
            document_id=document.id,
        )

    def to_dict(self) -> dict:
        return {
            "message_id": self.message_id,
            "thread_id": self.thread_id,
            "subject": self.subject,
            "sender": self.sender,
            "date": self.date,
            "connector_id": self.connector_id,
            "document_id": self.document_id,
        }


class GmailToolMetadataService:
    def __init__(self, db_session: AsyncSession):
        self._db_session = db_session

    async def _build_credentials(self, connector: SearchSourceConnector) -> Credentials:
        if (
            connector.connector_type
            == SearchSourceConnectorType.COMPOSIO_GMAIL_CONNECTOR
        ):
            cca_id = connector.config.get("composio_connected_account_id")
            if cca_id:
                return build_composio_credentials(cca_id)

        config_data = dict(connector.config)

        from app.config import config
        from app.utils.oauth_security import TokenEncryption

        token_encrypted = config_data.get("_token_encrypted", False)
        if token_encrypted and config.SECRET_KEY:
            token_encryption = TokenEncryption(config.SECRET_KEY)
            if config_data.get("token"):
                config_data["token"] = token_encryption.decrypt_token(
                    config_data["token"]
                )
            if config_data.get("refresh_token"):
                config_data["refresh_token"] = token_encryption.decrypt_token(
                    config_data["refresh_token"]
                )
            if config_data.get("client_secret"):
                config_data["client_secret"] = token_encryption.decrypt_token(
                    config_data["client_secret"]
                )

        exp = config_data.get("expiry", "")
        if exp:
            exp = exp.replace("Z", "")

        return Credentials(
            token=config_data.get("token"),
            refresh_token=config_data.get("refresh_token"),
            token_uri=config_data.get("token_uri"),
            client_id=config_data.get("client_id"),
            client_secret=config_data.get("client_secret"),
            scopes=config_data.get("scopes", []),
            expiry=datetime.fromisoformat(exp) if exp else None,
        )

    async def _check_account_health(self, connector_id: int) -> bool:
        """Check if a Gmail connector's credentials are still valid.

        Uses a lightweight ``users().getProfile(userId='me')`` call.

        Returns True if the credentials are expired/invalid, False if healthy.
        """
        try:
            result = await self._db_session.execute(
                select(SearchSourceConnector).where(
                    SearchSourceConnector.id == connector_id
                )
            )
            connector = result.scalar_one_or_none()
            if not connector:
                return True

            creds = await self._build_credentials(connector)
            service = build("gmail", "v1", credentials=creds)
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: service.users().getProfile(userId="me").execute()
            )
            return False
        except Exception as e:
            logger.warning(
                "Gmail connector %s health check failed: %s",
                connector_id,
                e,
            )
            return True

    async def _persist_auth_expired(self, connector_id: int) -> None:
        """Persist ``auth_expired: True`` to the connector config if not already set."""
        try:
            result = await self._db_session.execute(
                select(SearchSourceConnector).where(
                    SearchSourceConnector.id == connector_id
                )
            )
            db_connector = result.scalar_one_or_none()
            if db_connector and not db_connector.config.get("auth_expired"):
                db_connector.config = {**db_connector.config, "auth_expired": True}
                flag_modified(db_connector, "config")
                await self._db_session.commit()
                await self._db_session.refresh(db_connector)
        except Exception:
            logger.warning(
                "Failed to persist auth_expired for connector %s",
                connector_id,
                exc_info=True,
            )

    async def _get_accounts(
        self, search_space_id: int, user_id: str
    ) -> list[GmailAccount]:
        result = await self._db_session.execute(
            select(SearchSourceConnector)
            .filter(
                and_(
                    SearchSourceConnector.search_space_id == search_space_id,
                    SearchSourceConnector.user_id == user_id,
                    SearchSourceConnector.connector_type.in_(
                        [
                            SearchSourceConnectorType.GOOGLE_GMAIL_CONNECTOR,
                            SearchSourceConnectorType.COMPOSIO_GMAIL_CONNECTOR,
                        ]
                    ),
                )
            )
            .order_by(SearchSourceConnector.last_indexed_at.desc())
        )
        connectors = result.scalars().all()
        return [GmailAccount.from_connector(c) for c in connectors]

    async def get_creation_context(self, search_space_id: int, user_id: str) -> dict:
        accounts = await self._get_accounts(search_space_id, user_id)

        if not accounts:
            return {
                "accounts": [],
                "error": "No Gmail account connected",
            }

        accounts_with_status = []
        for acc in accounts:
            acc_dict = acc.to_dict()
            auth_expired = await self._check_account_health(acc.id)
            acc_dict["auth_expired"] = auth_expired
            if auth_expired:
                await self._persist_auth_expired(acc.id)
            else:
                try:
                    result = await self._db_session.execute(
                        select(SearchSourceConnector).where(
                            SearchSourceConnector.id == acc.id
                        )
                    )
                    connector = result.scalar_one_or_none()
                    if connector:
                        creds = await self._build_credentials(connector)
                        service = build("gmail", "v1", credentials=creds)
                        profile = await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda service=service: (
                                service.users().getProfile(userId="me").execute()
                            ),
                        )
                        acc_dict["email"] = profile.get("emailAddress", "")
                except Exception:
                    logger.warning(
                        "Failed to fetch email for Gmail connector %s",
                        acc.id,
                        exc_info=True,
                    )
            accounts_with_status.append(acc_dict)

        return {"accounts": accounts_with_status}

    async def get_update_context(
        self, search_space_id: int, user_id: str, email_ref: str
    ) -> dict:
        document, connector = await self._resolve_email(
            search_space_id, user_id, email_ref
        )

        if not document or not connector:
            return {
                "error": (
                    f"Draft '{email_ref}' not found in your indexed Gmail messages. "
                    "This could mean: (1) the draft doesn't exist, "
                    "(2) it hasn't been indexed yet, "
                    "or (3) the subject is different. "
                    "Please check the exact draft subject in Gmail."
                )
            }

        account = GmailAccount.from_connector(connector)
        message = GmailMessage.from_document(document)

        acc_dict = account.to_dict()
        auth_expired = await self._check_account_health(connector.id)
        acc_dict["auth_expired"] = auth_expired
        if auth_expired:
            await self._persist_auth_expired(connector.id)

        result: dict = {
            "account": acc_dict,
            "email": message.to_dict(),
        }

        meta = document.document_metadata or {}
        if meta.get("draft_id"):
            result["draft_id"] = meta["draft_id"]

        if not auth_expired:
            existing_body = await self._fetch_draft_body(
                connector, message.message_id, meta.get("draft_id")
            )
            if existing_body is not None:
                result["existing_body"] = existing_body

        return result

    async def _fetch_draft_body(
        self,
        connector: SearchSourceConnector,
        message_id: str,
        draft_id: str | None,
    ) -> str | None:
        """Fetch the plain-text body of a Gmail draft via the API.

        Tries ``drafts.get`` first (if *draft_id* is available), then falls
        back to scanning ``drafts.list`` to resolve the draft by *message_id*.
        Returns ``None`` on any failure so callers can degrade gracefully.
        """
        try:
            creds = await self._build_credentials(connector)
            service = build("gmail", "v1", credentials=creds)

            if not draft_id:
                draft_id = await self._find_draft_id(service, message_id)
            if not draft_id:
                return None

            draft = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: (
                    service.users()
                    .drafts()
                    .get(userId="me", id=draft_id, format="full")
                    .execute()
                ),
            )

            payload = draft.get("message", {}).get("payload", {})
            return self._extract_body_from_payload(payload)
        except Exception:
            logger.warning(
                "Failed to fetch draft body for message_id=%s",
                message_id,
                exc_info=True,
            )
            return None

    async def _find_draft_id(self, service: Any, message_id: str) -> str | None:
        """Resolve a draft ID from its message ID by scanning drafts.list."""
        try:
            page_token = None
            while True:
                kwargs: dict[str, Any] = {"userId": "me", "maxResults": 100}
                if page_token:
                    kwargs["pageToken"] = page_token
                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda kwargs=kwargs: (
                        service.users().drafts().list(**kwargs).execute()
                    ),
                )
                for draft in response.get("drafts", []):
                    if draft.get("message", {}).get("id") == message_id:
                        return draft["id"]
                page_token = response.get("nextPageToken")
                if not page_token:
                    break
            return None
        except Exception:
            logger.warning(
                "Failed to look up draft by message_id=%s", message_id, exc_info=True
            )
            return None

    @staticmethod
    def _extract_body_from_payload(payload: dict) -> str | None:
        """Extract the plain-text (or html→text) body from a Gmail payload."""
        import base64

        def _get_parts(p: dict) -> list[dict]:
            if "parts" in p:
                parts: list[dict] = []
                for sub in p["parts"]:
                    parts.extend(_get_parts(sub))
                return parts
            return [p]

        parts = _get_parts(payload)
        text_content = ""
        for part in parts:
            mime_type = part.get("mimeType", "")
            data = part.get("body", {}).get("data", "")
            if mime_type == "text/plain" and data:
                text_content += base64.urlsafe_b64decode(data + "===").decode(
                    "utf-8", errors="ignore"
                )
            elif mime_type == "text/html" and data and not text_content:
                from markdownify import markdownify as md

                raw_html = base64.urlsafe_b64decode(data + "===").decode(
                    "utf-8", errors="ignore"
                )
                text_content = md(raw_html).strip()

        return text_content.strip() if text_content.strip() else None

    async def get_trash_context(
        self, search_space_id: int, user_id: str, email_ref: str
    ) -> dict:
        document, connector = await self._resolve_email(
            search_space_id, user_id, email_ref
        )

        if not document or not connector:
            return {
                "error": (
                    f"Email '{email_ref}' not found in your indexed Gmail messages. "
                    "This could mean: (1) the email doesn't exist, "
                    "(2) it hasn't been indexed yet, "
                    "or (3) the subject is different."
                )
            }

        account = GmailAccount.from_connector(connector)
        message = GmailMessage.from_document(document)

        acc_dict = account.to_dict()
        auth_expired = await self._check_account_health(connector.id)
        acc_dict["auth_expired"] = auth_expired
        if auth_expired:
            await self._persist_auth_expired(connector.id)

        return {
            "account": acc_dict,
            "email": message.to_dict(),
        }

    async def _resolve_email(
        self, search_space_id: int, user_id: str, email_ref: str
    ) -> tuple[Document | None, SearchSourceConnector | None]:
        result = await self._db_session.execute(
            select(Document, SearchSourceConnector)
            .join(
                SearchSourceConnector,
                Document.connector_id == SearchSourceConnector.id,
            )
            .filter(
                and_(
                    Document.search_space_id == search_space_id,
                    Document.document_type.in_(
                        [
                            DocumentType.GOOGLE_GMAIL_CONNECTOR,
                            DocumentType.COMPOSIO_GMAIL_CONNECTOR,
                        ]
                    ),
                    SearchSourceConnector.user_id == user_id,
                    or_(
                        func.lower(cast(Document.document_metadata["subject"], String))
                        == func.lower(email_ref),
                        func.lower(Document.title) == func.lower(email_ref),
                    ),
                )
            )
            .order_by(Document.updated_at.desc().nullslast())
            .limit(1)
        )
        row = result.first()
        if row:
            return row[0], row[1]
        return None, None
