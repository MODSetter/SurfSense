import logging
from datetime import datetime

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.linear_connector import LinearConnector
from app.db import Chunk, Document
from app.services.llm_service import get_user_long_context_llm
from app.utils.document_converters import (
    create_document_chunks,
    embed_text,
    generate_content_hash,
    generate_document_summary,
)

logger = logging.getLogger(__name__)


class LinearKBSyncService:
    """Re-indexes a single Linear issue document after a successful update.

    Mirrors the indexer's Phase-2 logic exactly: fetch fresh issue content,
    run generate_document_summary, create_document_chunks, then update the
    document row in the knowledge base.
    """

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

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

            await self.db_session.execute(
                delete(Chunk).where(Chunk.document_id == document.id)
            )

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
            safe_set_chunks(document, chunks)
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
