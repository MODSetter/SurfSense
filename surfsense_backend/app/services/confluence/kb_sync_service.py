import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.confluence_history import ConfluenceHistoryConnector
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


class ConfluenceKBSyncService:
    """Syncs Confluence page documents to the knowledge base after HITL actions."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def sync_after_create(
        self,
        page_id: str,
        page_title: str,
        space_id: str,
        body_content: str | None,
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
                DocumentType.CONFLUENCE_CONNECTOR, page_id, search_space_id
            )

            existing = await check_document_by_unique_identifier(
                self.db_session, unique_hash
            )
            if existing:
                return {"status": "success"}

            indexable_content = (body_content or "").strip()
            if not indexable_content:
                indexable_content = f"Confluence Page: {page_title}"

            page_content = f"# {page_title}\n\n{indexable_content}"

            content_hash = generate_content_hash(page_content, search_space_id)

            with self.db_session.no_autoflush:
                dup = await check_duplicate_document_by_hash(
                    self.db_session, content_hash
                )
            if dup:
                content_hash = unique_hash

            user_llm = await get_user_long_context_llm(
                self.db_session,
                user_id,
                search_space_id,
                disable_streaming=True,
            )

            doc_metadata_for_summary = {
                "page_title": page_title,
                "space_id": space_id,
                "document_type": "Confluence Page",
                "connector_type": "Confluence",
            }

            if user_llm:
                summary_content, summary_embedding = await generate_document_summary(
                    page_content, user_llm, doc_metadata_for_summary
                )
            else:
                summary_content = f"Confluence Page: {page_title}\n\n{page_content}"
                summary_embedding = embed_text(summary_content)

            chunks = await create_document_chunks(page_content)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            document = Document(
                title=page_title,
                document_type=DocumentType.CONFLUENCE_CONNECTOR,
                document_metadata={
                    "page_id": page_id,
                    "page_title": page_title,
                    "space_id": space_id,
                    "comment_count": 0,
                    "indexed_at": now_str,
                    "connector_id": connector_id,
                },
                content=summary_content,
                content_hash=content_hash,
                unique_identifier_hash=unique_hash,
                embedding=summary_embedding,
                search_space_id=search_space_id,
                connector_id=connector_id,
                updated_at=get_current_timestamp(),
                created_by_id=user_id,
            )

            self.db_session.add(document)
            await self.db_session.flush()
            await safe_set_chunks(self.db_session, document, chunks)
            await self.db_session.commit()

            logger.info(
                "KB sync after create succeeded: doc_id=%s, page=%s",
                document.id,
                page_title,
            )
            return {"status": "success"}

        except Exception as e:
            error_str = str(e).lower()
            if (
                "duplicate key value violates unique constraint" in error_str
                or "uniqueviolationerror" in error_str
            ):
                await self.db_session.rollback()
                return {"status": "error", "message": "Duplicate document detected"}

            logger.error(
                "KB sync after create failed for page %s: %s",
                page_title,
                e,
                exc_info=True,
            )
            await self.db_session.rollback()
            return {"status": "error", "message": str(e)}

    async def sync_after_update(
        self,
        document_id: int,
        page_id: str,
        user_id: str,
        search_space_id: int,
    ) -> dict:
        from app.tasks.connector_indexers.base import (
            get_current_timestamp,
            safe_set_chunks,
        )

        try:
            document = await self.db_session.get(Document, document_id)
            if not document:
                return {"status": "not_indexed"}

            connector_id = document.connector_id
            if not connector_id:
                return {"status": "error", "message": "Document has no connector_id"}

            client = ConfluenceHistoryConnector(
                session=self.db_session, connector_id=connector_id
            )
            page_data = await client.get_page(page_id)
            await client.close()

            page_title = page_data.get("title", "")
            body_obj = page_data.get("body", {})
            body_content = ""
            if isinstance(body_obj, dict):
                storage = body_obj.get("storage", {})
                if isinstance(storage, dict):
                    body_content = storage.get("value", "")

            page_content = f"# {page_title}\n\n{body_content}"

            if not page_content.strip():
                return {"status": "error", "message": "Page produced empty content"}

            space_id = (document.document_metadata or {}).get("space_id", "")

            user_llm = await get_user_long_context_llm(
                self.db_session, user_id, search_space_id, disable_streaming=True
            )

            if user_llm:
                doc_meta = {
                    "page_title": page_title,
                    "space_id": space_id,
                    "document_type": "Confluence Page",
                    "connector_type": "Confluence",
                }
                summary_content, summary_embedding = await generate_document_summary(
                    page_content, user_llm, doc_meta
                )
            else:
                summary_content = f"Confluence Page: {page_title}\n\n{page_content}"
                summary_embedding = embed_text(summary_content)

            chunks = await create_document_chunks(page_content)

            document.title = page_title
            document.content = summary_content
            document.content_hash = generate_content_hash(page_content, search_space_id)
            document.embedding = summary_embedding

            from sqlalchemy.orm.attributes import flag_modified

            document.document_metadata = {
                **(document.document_metadata or {}),
                "page_id": page_id,
                "page_title": page_title,
                "space_id": space_id,
                "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "connector_id": connector_id,
            }
            flag_modified(document, "document_metadata")
            await safe_set_chunks(self.db_session, document, chunks)
            document.updated_at = get_current_timestamp()

            await self.db_session.commit()

            logger.info(
                "KB sync successful for document %s (%s)",
                document_id,
                page_title,
            )
            return {"status": "success"}

        except Exception as e:
            logger.error(
                "KB sync failed for document %s: %s", document_id, e, exc_info=True
            )
            await self.db_session.rollback()
            return {"status": "error", "message": str(e)}
