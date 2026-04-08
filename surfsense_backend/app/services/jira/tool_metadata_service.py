import asyncio
import logging
from dataclasses import dataclass

from sqlalchemy import and_, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm.attributes import flag_modified

from app.connectors.jira_history import JiraHistoryConnector
from app.db import (
    Document,
    DocumentType,
    SearchSourceConnector,
    SearchSourceConnectorType,
)

logger = logging.getLogger(__name__)


@dataclass
class JiraWorkspace:
    """Represents a Jira connector as a workspace for tool context."""

    id: int
    name: str
    base_url: str

    @classmethod
    def from_connector(cls, connector: SearchSourceConnector) -> "JiraWorkspace":
        return cls(
            id=connector.id,
            name=connector.name,
            base_url=connector.config.get("base_url", ""),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "base_url": self.base_url,
        }


@dataclass
class JiraIssue:
    """Represents an indexed Jira issue resolved from the knowledge base."""

    issue_id: str
    issue_identifier: str
    issue_title: str
    state: str
    connector_id: int
    document_id: int
    indexed_at: str | None

    @classmethod
    def from_document(cls, document: Document) -> "JiraIssue":
        meta = document.document_metadata or {}
        return cls(
            issue_id=meta.get("issue_id", ""),
            issue_identifier=meta.get("issue_identifier", ""),
            issue_title=meta.get("issue_title", document.title),
            state=meta.get("state", ""),
            connector_id=document.connector_id,
            document_id=document.id,
            indexed_at=meta.get("indexed_at"),
        )

    def to_dict(self) -> dict:
        return {
            "issue_id": self.issue_id,
            "issue_identifier": self.issue_identifier,
            "issue_title": self.issue_title,
            "state": self.state,
            "connector_id": self.connector_id,
            "document_id": self.document_id,
            "indexed_at": self.indexed_at,
        }


class JiraToolMetadataService:
    """Builds interrupt context for Jira HITL tools."""

    def __init__(self, db_session: AsyncSession):
        self._db_session = db_session

    async def _check_account_health(self, connector: SearchSourceConnector) -> bool:
        """Check if the Jira connector auth is still valid.

        Returns True if auth is expired/invalid, False if healthy.
        """
        try:
            jira_history = JiraHistoryConnector(
                session=self._db_session, connector_id=connector.id
            )
            jira_client = await jira_history._get_jira_client()
            await asyncio.to_thread(jira_client.get_myself)
            return False
        except Exception as e:
            logger.warning("Jira connector %s health check failed: %s", connector.id, e)
            try:
                connector.config = {**connector.config, "auth_expired": True}
                flag_modified(connector, "config")
                await self._db_session.commit()
                await self._db_session.refresh(connector)
            except Exception:
                logger.warning(
                    "Failed to persist auth_expired for connector %s",
                    connector.id,
                    exc_info=True,
                )
            return True

    async def get_creation_context(self, search_space_id: int, user_id: str) -> dict:
        """Return context needed to create a new Jira issue.

        Fetches all connected Jira accounts, and for the first healthy one
        fetches projects, issue types, and priorities.
        """
        connectors = await self._get_all_jira_connectors(search_space_id, user_id)
        if not connectors:
            return {"error": "No Jira account connected"}

        accounts = []
        projects = []
        issue_types = []
        priorities = []
        fetched_context = False

        for connector in connectors:
            auth_expired = await self._check_account_health(connector)
            workspace = JiraWorkspace.from_connector(connector)
            account_info = {
                **workspace.to_dict(),
                "auth_expired": auth_expired,
            }
            accounts.append(account_info)

            if not auth_expired and not fetched_context:
                try:
                    jira_history = JiraHistoryConnector(
                        session=self._db_session, connector_id=connector.id
                    )
                    jira_client = await jira_history._get_jira_client()
                    raw_projects = await asyncio.to_thread(jira_client.get_projects)
                    projects = [
                        {"id": p.get("id"), "key": p.get("key"), "name": p.get("name")}
                        for p in raw_projects
                    ]
                    raw_types = await asyncio.to_thread(jira_client.get_issue_types)
                    seen_type_names: set[str] = set()
                    issue_types = []
                    for t in raw_types:
                        if t.get("subtask", False):
                            continue
                        name = t.get("name")
                        if name not in seen_type_names:
                            seen_type_names.add(name)
                            issue_types.append({"id": t.get("id"), "name": name})
                    raw_priorities = await asyncio.to_thread(jira_client.get_priorities)
                    priorities = [
                        {"id": p.get("id"), "name": p.get("name")}
                        for p in raw_priorities
                    ]
                    fetched_context = True
                except Exception as e:
                    logger.warning(
                        "Failed to fetch Jira context for connector %s: %s",
                        connector.id,
                        e,
                    )

        return {
            "accounts": accounts,
            "projects": projects,
            "issue_types": issue_types,
            "priorities": priorities,
        }

    async def get_update_context(
        self, search_space_id: int, user_id: str, issue_ref: str
    ) -> dict:
        """Return context needed to update an indexed Jira issue.

        Resolves the issue from the KB, then fetches current details from the Jira API.
        """
        document = await self._resolve_issue(search_space_id, user_id, issue_ref)
        if not document:
            return {
                "error": f"Issue '{issue_ref}' not found in your synced Jira issues. "
                "Please make sure the issue is indexed in your knowledge base."
            }

        connector = await self._get_connector_for_document(document, user_id)
        if not connector:
            return {"error": "Connector not found or access denied"}

        auth_expired = await self._check_account_health(connector)
        if auth_expired:
            return {
                "error": "Jira authentication has expired. Please re-authenticate.",
                "auth_expired": True,
                "connector_id": connector.id,
            }

        workspace = JiraWorkspace.from_connector(connector)
        issue = JiraIssue.from_document(document)

        try:
            jira_history = JiraHistoryConnector(
                session=self._db_session, connector_id=connector.id
            )
            jira_client = await jira_history._get_jira_client()
            issue_data = await asyncio.to_thread(jira_client.get_issue, issue.issue_id)
            formatted = jira_client.format_issue(issue_data)
        except Exception as e:
            error_str = str(e).lower()
            if (
                "401" in error_str
                or "403" in error_str
                or "authentication" in error_str
            ):
                return {
                    "error": f"Failed to fetch Jira issue: {e!s}",
                    "auth_expired": True,
                    "connector_id": connector.id,
                }
            return {"error": f"Failed to fetch Jira issue: {e!s}"}

        return {
            "account": {**workspace.to_dict(), "auth_expired": False},
            "issue": {
                "issue_id": formatted.get("key", issue.issue_id),
                "issue_identifier": formatted.get("key", issue.issue_identifier),
                "issue_title": formatted.get("title", issue.issue_title),
                "state": formatted.get("status", "Unknown"),
                "priority": formatted.get("priority", "Unknown"),
                "issue_type": formatted.get("issue_type", "Unknown"),
                "assignee": formatted.get("assignee"),
                "description": formatted.get("description"),
                "project": formatted.get("project", ""),
                "document_id": issue.document_id,
                "indexed_at": issue.indexed_at,
            },
        }

    async def get_deletion_context(
        self, search_space_id: int, user_id: str, issue_ref: str
    ) -> dict:
        """Return context needed to delete a Jira issue (KB metadata only, no API call)."""
        document = await self._resolve_issue(search_space_id, user_id, issue_ref)
        if not document:
            return {
                "error": f"Issue '{issue_ref}' not found in your synced Jira issues. "
                "Please make sure the issue is indexed in your knowledge base."
            }

        connector = await self._get_connector_for_document(document, user_id)
        if not connector:
            return {"error": "Connector not found or access denied"}

        auth_expired = connector.config.get("auth_expired", False)
        workspace = JiraWorkspace.from_connector(connector)
        issue = JiraIssue.from_document(document)

        return {
            "account": {**workspace.to_dict(), "auth_expired": auth_expired},
            "issue": issue.to_dict(),
        }

    async def _resolve_issue(
        self, search_space_id: int, user_id: str, issue_ref: str
    ) -> Document | None:
        """Resolve an issue from KB: issue_identifier -> issue_title -> document.title."""
        ref_lower = issue_ref.lower()

        result = await self._db_session.execute(
            select(Document)
            .join(
                SearchSourceConnector, Document.connector_id == SearchSourceConnector.id
            )
            .filter(
                and_(
                    Document.search_space_id == search_space_id,
                    Document.document_type == DocumentType.JIRA_CONNECTOR,
                    SearchSourceConnector.user_id == user_id,
                    or_(
                        func.lower(
                            Document.document_metadata.op("->>")("issue_identifier")
                        )
                        == ref_lower,
                        func.lower(Document.document_metadata.op("->>")("issue_title"))
                        == ref_lower,
                        func.lower(Document.title) == ref_lower,
                    ),
                )
            )
            .order_by(Document.updated_at.desc().nullslast())
            .limit(1)
        )
        return result.scalars().first()

    async def _get_all_jira_connectors(
        self, search_space_id: int, user_id: str
    ) -> list[SearchSourceConnector]:
        result = await self._db_session.execute(
            select(SearchSourceConnector).filter(
                and_(
                    SearchSourceConnector.search_space_id == search_space_id,
                    SearchSourceConnector.user_id == user_id,
                    SearchSourceConnector.connector_type
                    == SearchSourceConnectorType.JIRA_CONNECTOR,
                )
            )
        )
        return result.scalars().all()

    async def _get_connector_for_document(
        self, document: Document, user_id: str
    ) -> SearchSourceConnector | None:
        if not document.connector_id:
            return None
        result = await self._db_session.execute(
            select(SearchSourceConnector).filter(
                and_(
                    SearchSourceConnector.id == document.connector_id,
                    SearchSourceConnector.user_id == user_id,
                )
            )
        )
        return result.scalars().first()
