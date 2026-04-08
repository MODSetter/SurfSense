import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, DocumentType
from app.services.llm_service import get_user_long_context_llm
from app.utils.document_converters import (
    create_document_chunks,
    embed_text,
    generate_content_hash,
    generate_document_summary,
    generate_unique_identifier_hash,
)

logger = logging.getLogger(__name__)


class GmailKBSyncService:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def sync_after_create(
        self,
        message_id: str,
        thread_id: str,
        subject: str,
        sender: str,
        date_str: str,
        body_text: str | None,
        connector_id: int,
        search_space_id: int,
        user_id: str,
        draft_id: str | None = None,
    ) -> dict:
        from app.tasks.connector_indexers.base import (
            check_document_by_unique_identifier,
            check_duplicate_document_by_hash,
            get_current_timestamp,
            safe_set_chunks,
        )

        try:
            unique_hash = generate_unique_identifier_hash(
                DocumentType.GOOGLE_GMAIL_CONNECTOR, message_id, search_space_id
            )

            existing = await check_document_by_unique_identifier(
                self.db_session, unique_hash
            )
            if existing:
                logger.info(
                    "Document for Gmail message %s already exists (doc_id=%s), skipping",
                    message_id,
                    existing.id,
                )
                return {"status": "success"}

            indexable_content = (
                f"Gmail Message: {subject}\n\nFrom: {sender}\nDate: {date_str}\n\n"
                f"{body_text or ''}"
            ).strip()
            if not indexable_content:
                indexable_content = f"Gmail message: {subject}"

            content_hash = generate_content_hash(indexable_content, search_space_id)

            with self.db_session.no_autoflush:
                dup = await check_duplicate_document_by_hash(
                    self.db_session, content_hash
                )
            if dup:
                logger.info(
                    "Content-hash collision for Gmail message %s -- identical content "
                    "exists in doc %s. Using unique_identifier_hash as content_hash.",
                    message_id,
                    dup.id,
                )
                content_hash = unique_hash

            user_llm = await get_user_long_context_llm(
                self.db_session,
                user_id,
                search_space_id,
                disable_streaming=True,
            )

            doc_metadata_for_summary = {
                "subject": subject,
                "sender": sender,
                "document_type": "Gmail Message",
                "connector_type": "Gmail",
            }

            if user_llm:
                summary_content, summary_embedding = await generate_document_summary(
                    indexable_content, user_llm, doc_metadata_for_summary
                )
            else:
                logger.warning("No LLM configured -- using fallback summary")
                summary_content = f"Gmail Message: {subject}\n\n{indexable_content}"
                summary_embedding = embed_text(summary_content)

            chunks = await create_document_chunks(indexable_content)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            doc_metadata = {
                "message_id": message_id,
                "thread_id": thread_id,
                "subject": subject,
                "sender": sender,
                "date": date_str,
                "connector_id": connector_id,
                "indexed_at": now_str,
            }
            if draft_id:
                doc_metadata["draft_id"] = draft_id

            document = Document(
                title=subject,
                document_type=DocumentType.GOOGLE_GMAIL_CONNECTOR,
                document_metadata=doc_metadata,
                content=summary_content,
                content_hash=content_hash,
                unique_identifier_hash=unique_hash,
                embedding=summary_embedding,
                search_space_id=search_space_id,
                connector_id=connector_id,
                source_markdown=body_text,
                updated_at=get_current_timestamp(),
                created_by_id=user_id,
            )

            self.db_session.add(document)
            await self.db_session.flush()
            await safe_set_chunks(self.db_session, document, chunks)
            await self.db_session.commit()

            logger.info(
                "KB sync after create succeeded: doc_id=%s, subject=%s, chunks=%d",
                document.id,
                subject,
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
                    "Duplicate constraint hit during KB sync for message %s. "
                    "Rolling back -- periodic indexer will handle it. Error: %s",
                    message_id,
                    e,
                )
                await self.db_session.rollback()
                return {"status": "error", "message": "Duplicate document detected"}

            logger.error(
                "KB sync after create failed for message %s: %s",
                message_id,
                e,
                exc_info=True,
            )
            await self.db_session.rollback()
            return {"status": "error", "message": str(e)}
