import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.linear_connector import LinearConnector
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


class LinearKBSyncService:
    """Syncs Linear issue documents to the knowledge base after HITL actions.

    Provides sync_after_create (new issue) and sync_after_update (existing issue).
    Both mirror the indexer's Phase-2 logic: generate summary, create chunks,
    then persist the document row.
    """

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def sync_after_create(
        self,
        issue_id: str,
        issue_identifier: str,
        issue_title: str,
        issue_url: str | None,
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
                DocumentType.LINEAR_CONNECTOR, issue_id, search_space_id
            )

            existing = await check_document_by_unique_identifier(
                self.db_session, unique_hash
            )
            if existing:
                logger.info(
                    "Document for Linear issue %s already exists (doc_id=%s), skipping",
                    issue_identifier,
                    existing.id,
                )
                return {"status": "success"}

            indexable_content = (description or "").strip()
            if not indexable_content:
                indexable_content = f"Linear Issue {issue_identifier}: {issue_title}"

            issue_content = (
                f"# {issue_identifier}: {issue_title}\n\n{indexable_content}"
            )

            content_hash = generate_content_hash(issue_content, search_space_id)

            with self.db_session.no_autoflush:
                dup = await check_duplicate_document_by_hash(
                    self.db_session, content_hash
                )
            if dup:
                logger.info(
                    "Content-hash collision for Linear issue %s — identical content "
                    "exists in doc %s. Using unique_identifier_hash as content_hash.",
                    issue_identifier,
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
                "issue_id": issue_identifier,
                "issue_title": issue_title,
                "document_type": "Linear Issue",
                "connector_type": "Linear",
            }

            if user_llm:
                summary_content, summary_embedding = await generate_document_summary(
                    issue_content, user_llm, doc_metadata_for_summary
                )
            else:
                logger.warning("No LLM configured — using fallback summary")
                summary_content = (
                    f"Linear Issue {issue_identifier}: {issue_title}\n\n{issue_content}"
                )
                summary_embedding = embed_text(summary_content)

            chunks = await create_document_chunks(issue_content)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            document = Document(
                title=f"{issue_identifier}: {issue_title}",
                document_type=DocumentType.LINEAR_CONNECTOR,
                document_metadata={
                    "issue_id": issue_id,
                    "issue_identifier": issue_identifier,
                    "issue_title": issue_title,
                    "issue_url": issue_url,
                    "source_connector": "linear",
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
                "KB sync after create succeeded: doc_id=%s, issue=%s, chunks=%d",
                document.id,
                issue_identifier,
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
                    "Duplicate constraint hit during KB sync for issue %s. "
                    "Rolling back — periodic indexer will handle it. Error: %s",
                    issue_identifier,
                    e,
                )
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
        """Re-index a Linear issue document after it has been updated via the API.

        Args:
            document_id: The KB document ID to update.
            issue_id: The Linear issue UUID to fetch fresh content from.
            user_id: Used to select the correct LLM configuration.
            search_space_id: Used to select the correct LLM configuration.

        Returns:
            dict with 'status': 'success' | 'not_indexed' | 'error'.
        """
        from app.tasks.connector_indexers.base import (
            get_current_timestamp,
            safe_set_chunks,
        )

        try:
            document = await self.db_session.get(Document, document_id)
            if not document:
                logger.warning(f"Document {document_id} not found in KB")
                return {"status": "not_indexed"}

            connector_id = document.connector_id
            if not connector_id:
                return {"status": "error", "message": "Document has no connector_id"}

            linear_client = LinearConnector(
                session=self.db_session, connector_id=connector_id
            )

            issue_raw = await self._fetch_issue(linear_client, issue_id)
            if not issue_raw:
                return {"status": "error", "message": "Issue not found in Linear API"}

            formatted_issue = linear_client.format_issue(issue_raw)
            issue_content = linear_client.format_issue_to_markdown(formatted_issue)

            if not issue_content:
                return {"status": "error", "message": "Issue produced empty content"}

            issue_identifier = formatted_issue.get("identifier", "")
            issue_title = formatted_issue.get("title", "")
            state = formatted_issue.get("state", "Unknown")
            priority = issue_raw.get("priorityLabel", "Unknown")
            comment_count = len(formatted_issue.get("comments", []))
            formatted_issue.get("description", "")

            user_llm = await get_user_long_context_llm(
                self.db_session, user_id, search_space_id, disable_streaming=True
            )

            if user_llm:
                document_metadata_for_summary = {
                    "issue_id": issue_identifier,
                    "issue_title": issue_title,
                    "state": state,
                    "priority": priority,
                    "comment_count": comment_count,
                    "document_type": "Linear Issue",
                    "connector_type": "Linear",
                }
                summary_content, summary_embedding = await generate_document_summary(
                    issue_content, user_llm, document_metadata_for_summary
                )
            else:
                summary_content = (
                    f"Linear Issue {issue_identifier}: {issue_title}\n\n{issue_content}"
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
                "priority": priority,
                "comment_count": comment_count,
                "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "connector_id": connector_id,
            }
            flag_modified(document, "document_metadata")
            await safe_set_chunks(self.db_session, document, chunks)
            document.updated_at = get_current_timestamp()

            await self.db_session.commit()

            logger.info(
                f"KB sync successful for document {document_id} "
                f"({issue_identifier}: {issue_title})"
            )
            return {"status": "success"}

        except Exception as e:
            logger.error(
                f"KB sync failed for document {document_id}: {e}", exc_info=True
            )
            await self.db_session.rollback()
            return {"status": "error", "message": str(e)}

    @staticmethod
    async def _fetch_issue(client: LinearConnector, issue_id: str) -> dict | None:
        """Fetch a full issue from Linear, matching the fields used by format_issue."""
        query = """
        query LinearIssueSync($id: String!) {
            issue(id: $id) {
                id identifier title description priority priorityLabel
                createdAt updatedAt url
                state { id name type color }
                creator { id name email }
                assignee { id name email }
                comments {
                    nodes {
                        id body createdAt updatedAt
                        user { id name email }
                    }
                }
                team { id name key }
            }
        }
        """
        result = await client.execute_graphql_query(query, {"id": issue_id})
        return (result.get("data") or {}).get("issue")
