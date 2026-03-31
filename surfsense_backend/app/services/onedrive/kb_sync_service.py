import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, DocumentType
from app.indexing_pipeline.document_hashing import compute_identifier_hash
from app.services.llm_service import get_user_long_context_llm
from app.utils.document_converters import (
    create_document_chunks,
    embed_text,
    generate_content_hash,
    generate_document_summary,
)

logger = logging.getLogger(__name__)


class OneDriveKBSyncService:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def sync_after_create(
        self,
        file_id: str,
        file_name: str,
        mime_type: str,
        web_url: str | None,
        content: str | None,
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
            unique_hash = compute_identifier_hash(
                DocumentType.ONEDRIVE_FILE.value, file_id, search_space_id
            )

            existing = await check_document_by_unique_identifier(
                self.db_session, unique_hash
            )
            if existing:
                logger.info(
                    "Document for OneDrive file %s already exists (doc_id=%s), skipping",
                    file_id,
                    existing.id,
                )
                return {"status": "success"}

            indexable_content = (content or "").strip()
            if not indexable_content:
                indexable_content = f"OneDrive file: {file_name} (type: {mime_type})"

            content_hash = generate_content_hash(indexable_content, search_space_id)

            with self.db_session.no_autoflush:
                dup = await check_duplicate_document_by_hash(
                    self.db_session, content_hash
                )
            if dup:
                logger.info(
                    "Content-hash collision for OneDrive file %s — identical content "
                    "exists in doc %s. Using unique_identifier_hash as content_hash.",
                    file_id,
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
                "file_name": file_name,
                "mime_type": mime_type,
                "document_type": "OneDrive File",
                "connector_type": "OneDrive",
            }

            if user_llm:
                summary_content, summary_embedding = await generate_document_summary(
                    indexable_content, user_llm, doc_metadata_for_summary
                )
            else:
                logger.warning("No LLM configured — using fallback summary")
                summary_content = f"OneDrive File: {file_name}\n\n{indexable_content}"
                summary_embedding = embed_text(summary_content)

            chunks = await create_document_chunks(indexable_content)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            document = Document(
                title=file_name,
                document_type=DocumentType.ONEDRIVE_FILE,
                document_metadata={
                    "onedrive_file_id": file_id,
                    "onedrive_file_name": file_name,
                    "onedrive_mime_type": mime_type,
                    "web_url": web_url,
                    "source_connector": "onedrive",
                    "indexed_at": now_str,
                    "connector_id": connector_id,
                },
                content=summary_content,
                content_hash=content_hash,
                unique_identifier_hash=unique_hash,
                embedding=summary_embedding,
                search_space_id=search_space_id,
                connector_id=connector_id,
                source_markdown=content,
                updated_at=get_current_timestamp(),
                created_by_id=user_id,
            )

            self.db_session.add(document)
            await self.db_session.flush()
            await safe_set_chunks(self.db_session, document, chunks)
            await self.db_session.commit()

            logger.info(
                "KB sync after create succeeded: doc_id=%s, file=%s, chunks=%d",
                document.id,
                file_name,
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
                    "Duplicate constraint hit during KB sync for file %s. "
                    "Rolling back — periodic indexer will handle it. Error: %s",
                    file_id,
                    e,
                )
                await self.db_session.rollback()
                return {"status": "error", "message": "Duplicate document detected"}

            logger.error(
                "KB sync after create failed for file %s: %s",
                file_id,
                e,
                exc_info=True,
            )
            await self.db_session.rollback()
            return {"status": "error", "message": str(e)}
