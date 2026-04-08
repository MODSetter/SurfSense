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


class NotionKBSyncService:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def sync_after_create(
        self,
        page_id: str,
        page_title: str,
        page_url: str | None,
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
            unique_hash = generate_unique_identifier_hash(
                DocumentType.NOTION_CONNECTOR, page_id, search_space_id
            )

            existing = await check_document_by_unique_identifier(
                self.db_session, unique_hash
            )
            if existing:
                logger.info(
                    "Document for Notion page %s already exists (doc_id=%s), skipping",
                    page_id,
                    existing.id,
                )
                return {"status": "success"}

            indexable_content = (content or "").strip()
            if not indexable_content:
                indexable_content = f"Notion Page: {page_title}"

            markdown_content = f"# Notion Page: {page_title}\n\n{indexable_content}"

            content_hash = generate_content_hash(markdown_content, search_space_id)

            with self.db_session.no_autoflush:
                dup = await check_duplicate_document_by_hash(
                    self.db_session, content_hash
                )
            if dup:
                logger.info(
                    "Content-hash collision for Notion page %s — identical content "
                    "exists in doc %s. Using unique_identifier_hash as content_hash.",
                    page_id,
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
                "page_title": page_title,
                "page_id": page_id,
                "document_type": "Notion Page",
                "connector_type": "Notion",
            }

            if user_llm:
                summary_content, summary_embedding = await generate_document_summary(
                    markdown_content, user_llm, doc_metadata_for_summary
                )
            else:
                logger.warning("No LLM configured — using fallback summary")
                summary_content = f"Notion Page: {page_title}\n\n{markdown_content}"
                summary_embedding = embed_text(summary_content)

            chunks = await create_document_chunks(markdown_content)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            document = Document(
                title=page_title,
                document_type=DocumentType.NOTION_CONNECTOR,
                document_metadata={
                    "page_title": page_title,
                    "page_id": page_id,
                    "page_url": page_url,
                    "source_connector": "notion",
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
                "KB sync after create succeeded: doc_id=%s, page=%s, chunks=%d",
                document.id,
                page_title,
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
                    "Duplicate constraint hit during KB sync for page %s. "
                    "Rolling back — periodic indexer will handle it. Error: %s",
                    page_id,
                    e,
                )
                await self.db_session.rollback()
                return {"status": "error", "message": "Duplicate document detected"}

            logger.error(
                "KB sync after create failed for page %s: %s",
                page_id,
                e,
                exc_info=True,
            )
            await self.db_session.rollback()
            return {"status": "error", "message": str(e)}

    async def sync_after_update(
        self,
        document_id: int,
        appended_content: str,
        user_id: str,
        search_space_id: int,
        appended_block_ids: list[str] | None = None,
    ) -> dict:
        from app.tasks.connector_indexers.base import (
            get_current_timestamp,
            safe_set_chunks,
        )

        try:
            logger.debug(f"Starting KB sync for document {document_id}")
            document = await self.db_session.get(Document, document_id)

            if not document:
                logger.warning(f"Document {document_id} not found in KB")
                return {"status": "not_indexed"}

            page_id = document.document_metadata.get("page_id")
            if not page_id:
                logger.error(f"Document {document_id} missing page_id in metadata")
                return {"status": "error", "message": "Missing page_id in metadata"}

            logger.debug(
                f"Document found: id={document_id}, page_id={page_id}, connector_id={document.connector_id}"
            )

            from app.connectors.notion_history import NotionHistoryConnector

            notion_connector = NotionHistoryConnector(
                session=self.db_session, connector_id=document.connector_id
            )

            logger.debug(f"Fetching page content from Notion for page {page_id}")
            blocks, _ = await notion_connector.get_page_content(
                page_id, page_title=None
            )

            from app.utils.notion_utils import extract_all_block_ids, process_blocks

            fetched_content = process_blocks(blocks)
            logger.debug(f"Fetched content length: {len(fetched_content)} chars")

            if not fetched_content or not fetched_content.strip():
                logger.warning(
                    f"Fetched empty content for page {page_id} - document will have minimal searchable text"
                )

            content_verified = False
            if appended_block_ids:
                fetched_block_ids = set(extract_all_block_ids(blocks))
                found_blocks = [
                    bid for bid in appended_block_ids if bid in fetched_block_ids
                ]

                logger.debug(
                    f"Block verification: {len(found_blocks)}/{len(appended_block_ids)} blocks found"
                )
                logger.debug(
                    f"Appended IDs (first 3): {appended_block_ids[:3]}, Fetched IDs count: {len(fetched_block_ids)}"
                )

                if len(found_blocks) >= len(appended_block_ids) * 0.8:  # 80% threshold
                    logger.info(
                        f"Content verified fresh: found {len(found_blocks)}/{len(appended_block_ids)} appended blocks"
                    )
                    full_content = fetched_content
                    content_verified = True
                else:
                    logger.warning(
                        "No appended blocks found in fetched content - appending manually"
                    )
                    full_content = fetched_content + "\n\n" + appended_content
                    content_verified = False
            else:
                logger.warning("No block IDs provided - using fetched content as-is")
                full_content = fetched_content
                content_verified = False

            logger.debug(
                f"Final content length: {len(full_content)} chars, verified={content_verified}"
            )

            logger.debug("Generating summary and embeddings")
            user_llm = await get_user_long_context_llm(
                self.db_session,
                user_id,
                search_space_id,
                disable_streaming=True,  # disable streaming to avoid leaking into the chat
            )

            if user_llm:
                document_metadata_for_summary = {
                    "page_title": document.document_metadata.get("page_title"),
                    "page_id": document.document_metadata.get("page_id"),
                    "document_type": "Notion Page",
                    "connector_type": "Notion",
                }
                summary_content, summary_embedding = await generate_document_summary(
                    full_content, user_llm, document_metadata_for_summary
                )
                logger.debug(f"Generated summary length: {len(summary_content)} chars")
            else:
                logger.warning("No LLM configured - using fallback summary")
                summary_content = f"Notion Page: {document.document_metadata.get('page_title')}\n\n{full_content}"
                summary_embedding = embed_text(summary_content)

            logger.debug("Creating new chunks")
            chunks = await create_document_chunks(full_content)
            logger.debug(f"Created {len(chunks)} chunks")

            logger.debug("Updating document fields")
            document.content = summary_content
            document.content_hash = generate_content_hash(full_content, search_space_id)
            document.embedding = summary_embedding
            document.document_metadata = {
                **document.document_metadata,
                "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            await safe_set_chunks(self.db_session, document, chunks)
            document.updated_at = get_current_timestamp()

            logger.debug("Committing changes to database")
            await self.db_session.commit()

            logger.info(
                f"Successfully synced KB for document {document_id}: "
                f"summary={len(summary_content)} chars, chunks={len(chunks)}, "
                f"content_verified={content_verified}"
            )
            return {"status": "success"}

        except Exception as e:
            logger.error(
                f"Failed to sync KB for document {document_id}: {e}", exc_info=True
            )
            await self.db_session.rollback()
            return {"status": "error", "message": str(e)}
