import asyncio
import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.jira_history import JiraHistoryConnector
from app.db import Document, DocumentType
from app.utils.document_converters import (
    create_document_chunks,
    embed_text,
    generate_content_hash,
    generate_document_summary,
    generate_unique_identifier_hash,
)

logger = logging.getLogger(__name__)


class JiraKBSyncService:
    """Syncs Jira issue documents to the knowledge base after HITL actions."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def sync_after_create(
        self,
        issue_id: str,
        issue_identifier: str,
        issue_title: str,
        description: str | None,
        state: str | None,
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
                DocumentType.JIRA_CONNECTOR, issue_id, search_space_id
            )

            existing = await check_document_by_unique_identifier(
                self.db_session, unique_hash
            )
            if existing:
                logger.info(
                    "Document for Jira issue %s already exists (doc_id=%s), skipping",
                    issue_identifier,
                    existing.id,
                )
                return {"status": "success"}

            indexable_content = (description or "").strip()
            if not indexable_content:
                indexable_content = f"Jira Issue {issue_identifier}: {issue_title}"

            issue_content = (
                f"# {issue_identifier}: {issue_title}\n\n{indexable_content}"
            )

            content_hash = generate_content_hash(issue_content, search_space_id)

            with self.db_session.no_autoflush:
                dup = await check_duplicate_document_by_hash(
                    self.db_session, content_hash
                )
            if dup:
                content_hash = unique_hash

            from app.services.llm_service import get_user_long_context_llm

            user_llm = await get_user_long_context_llm(
                self.db_session,
                user_id,
                search_space_id,
                disable_streaming=True,
            )

            doc_metadata_for_summary = {
                "issue_id": issue_identifier,
                "issue_title": issue_title,
                "document_type": "Jira Issue",
                "connector_type": "Jira",
            }

            if user_llm:
                summary_content, summary_embedding = await generate_document_summary(
                    issue_content, user_llm, doc_metadata_for_summary
                )
            else:
                summary_content = (
                    f"Jira Issue {issue_identifier}: {issue_title}\n\n{issue_content}"
                )
                summary_embedding = embed_text(summary_content)

            chunks = await create_document_chunks(issue_content)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            document = Document(
                title=f"{issue_identifier}: {issue_title}",
                document_type=DocumentType.JIRA_CONNECTOR,
                document_metadata={
                    "issue_id": issue_id,
                    "issue_identifier": issue_identifier,
                    "issue_title": issue_title,
                    "state": state or "Unknown",
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
                "KB sync after create succeeded: doc_id=%s, issue=%s",
                document.id,
                issue_identifier,
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
                "KB sync after create failed for issue %s: %s",
                issue_identifier,
                e,
                exc_info=True,
            )
            await self.db_session.rollback()
            return {"status": "error", "message": str(e)}

    async def sync_after_update(
        self,
        document_id: int,
        issue_id: str,
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

            jira_history = JiraHistoryConnector(
                session=self.db_session, connector_id=connector_id
            )
            jira_client = await jira_history._get_jira_client()
            issue_raw = await asyncio.to_thread(jira_client.get_issue, issue_id)
            formatted = jira_client.format_issue(issue_raw)
            issue_content = jira_client.format_issue_to_markdown(formatted)

            if not issue_content:
                return {"status": "error", "message": "Issue produced empty content"}

            issue_identifier = formatted.get("key", "")
            issue_title = formatted.get("title", "")
            state = formatted.get("status", "Unknown")
            comment_count = len(formatted.get("comments", []))

            from app.services.llm_service import get_user_long_context_llm

            user_llm = await get_user_long_context_llm(
                self.db_session, user_id, search_space_id, disable_streaming=True
            )

            if user_llm:
                doc_meta = {
                    "issue_key": issue_identifier,
                    "issue_title": issue_title,
                    "status": state,
                    "document_type": "Jira Issue",
                    "connector_type": "Jira",
                }
                summary_content, summary_embedding = await generate_document_summary(
                    issue_content, user_llm, doc_meta
                )
            else:
                summary_content = (
                    f"Jira Issue {issue_identifier}: {issue_title}\n\n{issue_content}"
                )
                summary_embedding = embed_text(summary_content)

            chunks = await create_document_chunks(issue_content)

            document.title = f"{issue_identifier}: {issue_title}"
            document.content = summary_content
            document.content_hash = generate_content_hash(
                issue_content, search_space_id
            )
            document.embedding = summary_embedding

            from sqlalchemy.orm.attributes import flag_modified

            document.document_metadata = {
                **(document.document_metadata or {}),
                "issue_id": issue_id,
                "issue_identifier": issue_identifier,
                "issue_title": issue_title,
                "state": state,
                "comment_count": comment_count,
                "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "connector_id": connector_id,
            }
            flag_modified(document, "document_metadata")
            await safe_set_chunks(self.db_session, document, chunks)
            document.updated_at = get_current_timestamp()

            await self.db_session.commit()

            logger.info(
                "KB sync successful for document %s (%s: %s)",
                document_id,
                issue_identifier,
                issue_title,
            )
            return {"status": "success"}

        except Exception as e:
            logger.error(
                "KB sync failed for document %s: %s", document_id, e, exc_info=True
            )
            await self.db_session.rollback()
            return {"status": "error", "message": str(e)}
