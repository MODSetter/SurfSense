import asyncio
import logging
from datetime import datetime

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm.attributes import flag_modified

from app.db import (
    Document,
    DocumentType,
    SearchSourceConnector,
    SearchSourceConnectorType,
)
from app.utils.document_converters import (
    create_document_chunks,
    embed_text,
    generate_content_hash,
    generate_document_summary,
    generate_unique_identifier_hash,
)
from app.utils.google_credentials import build_composio_credentials

logger = logging.getLogger(__name__)


class GoogleCalendarKBSyncService:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def sync_after_create(
        self,
        event_id: str,
        event_summary: str,
        calendar_id: str,
        start_time: str,
        end_time: str,
        location: str | None,
        html_link: str | None,
        description: str | None,
        connector_id: int,
        search_space_id: int,
        user_id: str,
    ) -> dict:
        from app.tasks.connector_indexers.base import (
            check_document_by_unique_identifier,
            check_duplicate_document_by_hash,
            get_current_timestamp,
            safe_set_chunks,
        )

        try:
            unique_hash = generate_unique_identifier_hash(
                DocumentType.GOOGLE_CALENDAR_CONNECTOR, event_id, search_space_id
            )

            existing = await check_document_by_unique_identifier(
                self.db_session, unique_hash
            )
            if existing:
                logger.info(
                    "Document for Calendar event %s already exists (doc_id=%s), skipping",
                    event_id,
                    existing.id,
                )
                return {"status": "success"}

            indexable_content = (
                f"Google Calendar Event: {event_summary}\n\n"
                f"Start: {start_time}\n"
                f"End: {end_time}\n"
                f"Location: {location or 'N/A'}\n\n"
                f"{description or ''}"
            ).strip()

            content_hash = generate_content_hash(indexable_content, search_space_id)

            with self.db_session.no_autoflush:
                dup = await check_duplicate_document_by_hash(
                    self.db_session, content_hash
                )
            if dup:
                logger.info(
                    "Content-hash collision for Calendar event %s -- identical content "
                    "exists in doc %s. Using unique_identifier_hash as content_hash.",
                    event_id,
                    dup.id,
                )
                content_hash = unique_hash

            from app.services.llm_service import get_user_long_context_llm

            user_llm = await get_user_long_context_llm(
                self.db_session,
                user_id,
                search_space_id,
                disable_streaming=True,
            )

            doc_metadata_for_summary = {
                "event_summary": event_summary,
                "start_time": start_time,
                "end_time": end_time,
                "document_type": "Google Calendar Event",
                "connector_type": "Google Calendar",
            }

            if user_llm:
                summary_content, summary_embedding = await generate_document_summary(
                    indexable_content, user_llm, doc_metadata_for_summary
                )
            else:
                logger.warning("No LLM configured -- using fallback summary")
                summary_content = (
                    f"Google Calendar Event: {event_summary}\n\n{indexable_content}"
                )
                summary_embedding = embed_text(summary_content)

            chunks = await create_document_chunks(indexable_content)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            document = Document(
                title=event_summary,
                document_type=DocumentType.GOOGLE_CALENDAR_CONNECTOR,
                document_metadata={
                    "event_id": event_id,
                    "event_summary": event_summary,
                    "calendar_id": calendar_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "location": location,
                    "html_link": html_link,
                    "source_connector": "google_calendar",
                    "indexed_at": now_str,
                    "connector_id": connector_id,
                },
                content=summary_content,
                content_hash=content_hash,
                unique_identifier_hash=unique_hash,
                embedding=summary_embedding,
                search_space_id=search_space_id,
                connector_id=connector_id,
                source_markdown=indexable_content,
                updated_at=get_current_timestamp(),
                created_by_id=user_id,
            )

            self.db_session.add(document)
            await self.db_session.flush()
            await safe_set_chunks(self.db_session, document, chunks)
            await self.db_session.commit()

            logger.info(
                "KB sync after create succeeded: doc_id=%s, event=%s, chunks=%d",
                document.id,
                event_summary,
                len(chunks),
            )
            return {"status": "success"}

        except Exception as e:
            error_str = str(e).lower()
            if (
                "duplicate key value violates unique constraint" in error_str
                or "uniqueviolationerror" in error_str
            ):
                logger.warning(
                    "Duplicate constraint hit during KB sync for event %s. "
                    "Rolling back -- periodic indexer will handle it. Error: %s",
                    event_id,
                    e,
                )
                await self.db_session.rollback()
                return {"status": "error", "message": "Duplicate document detected"}

            logger.error(
                "KB sync after create failed for event %s: %s",
                event_id,
                e,
                exc_info=True,
            )
            await self.db_session.rollback()
            return {"status": "error", "message": str(e)}

    async def sync_after_update(
        self,
        document_id: int,
        event_id: str,
        connector_id: int,
        search_space_id: int,
        user_id: str,
    ) -> dict:
        from app.tasks.connector_indexers.base import (
            get_current_timestamp,
            safe_set_chunks,
        )

        try:
            document = await self.db_session.get(Document, document_id)
            if not document:
                logger.warning("Document %s not found in KB", document_id)
                return {"status": "not_indexed"}

            creds = await self._build_credentials_for_connector(connector_id)
            loop = asyncio.get_event_loop()
            service = await loop.run_in_executor(
                None, lambda: build("calendar", "v3", credentials=creds)
            )

            calendar_id = (document.document_metadata or {}).get(
                "calendar_id"
            ) or "primary"
            live_event = await loop.run_in_executor(
                None,
                lambda: (
                    service.events()
                    .get(calendarId=calendar_id, eventId=event_id)
                    .execute()
                ),
            )

            event_summary = live_event.get("summary", "")
            description = live_event.get("description", "")
            location = live_event.get("location", "")

            start_data = live_event.get("start", {})
            start_time = start_data.get("dateTime", start_data.get("date", ""))

            end_data = live_event.get("end", {})
            end_time = end_data.get("dateTime", end_data.get("date", ""))

            attendees = [
                {
                    "email": a.get("email", ""),
                    "responseStatus": a.get("responseStatus", ""),
                }
                for a in live_event.get("attendees", [])
            ]

            indexable_content = (
                f"Google Calendar Event: {event_summary}\n\n"
                f"Start: {start_time}\n"
                f"End: {end_time}\n"
                f"Location: {location or 'N/A'}\n\n"
                f"{description or ''}"
            ).strip()

            if not indexable_content:
                return {"status": "error", "message": "Event produced empty content"}

            from app.services.llm_service import get_user_long_context_llm

            user_llm = await get_user_long_context_llm(
                self.db_session, user_id, search_space_id, disable_streaming=True
            )

            doc_metadata_for_summary = {
                "event_summary": event_summary,
                "start_time": start_time,
                "end_time": end_time,
                "document_type": "Google Calendar Event",
                "connector_type": "Google Calendar",
            }

            if user_llm:
                summary_content, summary_embedding = await generate_document_summary(
                    indexable_content, user_llm, doc_metadata_for_summary
                )
            else:
                summary_content = (
                    f"Google Calendar Event: {event_summary}\n\n{indexable_content}"
                )
                summary_embedding = embed_text(summary_content)

            chunks = await create_document_chunks(indexable_content)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            document.title = event_summary
            document.content = summary_content
            document.content_hash = generate_content_hash(
                indexable_content, search_space_id
            )
            document.embedding = summary_embedding

            document.document_metadata = {
                **(document.document_metadata or {}),
                "event_id": event_id,
                "event_summary": event_summary,
                "calendar_id": calendar_id,
                "start_time": start_time,
                "end_time": end_time,
                "location": location,
                "description": description,
                "attendees": attendees,
                "html_link": live_event.get("htmlLink", ""),
                "indexed_at": now_str,
                "connector_id": connector_id,
            }
            flag_modified(document, "document_metadata")

            await safe_set_chunks(self.db_session, document, chunks)
            document.updated_at = get_current_timestamp()

            await self.db_session.commit()

            logger.info(
                "KB sync after update succeeded for document %s (event: %s)",
                document_id,
                event_summary,
            )
            return {"status": "success"}

        except Exception as e:
            logger.error(
                "KB sync after update failed for document %s: %s",
                document_id,
                e,
                exc_info=True,
            )
            await self.db_session.rollback()
            return {"status": "error", "message": str(e)}

    async def _build_credentials_for_connector(self, connector_id: int) -> Credentials:
        result = await self.db_session.execute(
            select(SearchSourceConnector).where(
                SearchSourceConnector.id == connector_id
            )
        )
        connector = result.scalar_one_or_none()
        if not connector:
            raise ValueError(f"Connector {connector_id} not found")

        if (
            connector.connector_type
            == SearchSourceConnectorType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR
        ):
            cca_id = connector.config.get("composio_connected_account_id")
            if cca_id:
                return build_composio_credentials(cca_id)
            raise ValueError("Composio connected_account_id not found")

        config_data = dict(connector.config)

        from app.config import config as app_config
        from app.utils.oauth_security import TokenEncryption

        token_encrypted = config_data.get("_token_encrypted", False)
        if token_encrypted and app_config.SECRET_KEY:
            token_encryption = TokenEncryption(app_config.SECRET_KEY)
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
