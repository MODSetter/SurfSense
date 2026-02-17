import logging
from datetime import datetime

from sqlalchemy import String, cast, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import config
from app.db import Chunk, Document
from app.services.llm_service import get_user_long_context_llm
from app.utils.document_converters import (
    create_document_chunks,
    generate_content_hash,
    generate_document_summary,
)

logger = logging.getLogger(__name__)


class NotionKBSyncService:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def sync_after_update(
        self,
        page_id: str,
        search_space_id: int,
        appended_content: str,
        user_id: str,
    ) -> dict:
        from app.tasks.connector_indexers.base import (
            get_current_timestamp,
            safe_set_chunks,
        )

        try:
            result = await self.db_session.execute(
                select(Document).filter(
                    Document.search_space_id == search_space_id,
                    cast(Document.document_metadata["page_id"], String) == page_id,
                )
            )
            document = result.scalars().first()

            if not document:
                return {"status": "not_indexed"}

            new_content = document.content + "\n\n" + appended_content

            user_llm = await get_user_long_context_llm(
                self.db_session, user_id, search_space_id
            )

            if user_llm:
                document_metadata_for_summary = {
                    "page_title": document.document_metadata.get("page_title"),
                    "page_id": page_id,
                    "document_type": "Notion Page",
                    "connector_type": "Notion",
                }
                summary_content, summary_embedding = await generate_document_summary(
                    new_content, user_llm, document_metadata_for_summary
                )
            else:
                summary_content = f"Notion Page: {document.document_metadata.get('page_title')}\n\n{new_content[:500]}..."
                summary_embedding = config.embedding_model_instance.embed(
                    summary_content
                )

            await self.db_session.execute(
                delete(Chunk).where(Chunk.document_id == document.id)
            )

            chunks = await create_document_chunks(new_content)

            document.content = summary_content
            document.content_hash = generate_content_hash(new_content)
            document.embedding = summary_embedding
            document.document_metadata = {
                **document.document_metadata,
                "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            safe_set_chunks(document, chunks)
            document.updated_at = get_current_timestamp()

            await self.db_session.commit()

            logger.info(f"Successfully synced KB for Notion page {page_id}")
            return {"status": "success"}

        except Exception as e:
            logger.error(f"Failed to sync KB for page {page_id}: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}
