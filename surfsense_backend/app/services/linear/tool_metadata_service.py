from dataclasses import dataclass

from sqlalchemy import String, and_, cast, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.connectors.linear_connector import LinearConnector
from app.db import (
    Document,
    DocumentType,
    SearchSourceConnector,
    SearchSourceConnectorType,
)


@dataclass
class LinearWorkspace:
    """Represents a Linear connector as a workspace for tool context."""

    id: int
    name: str
    organization_name: str

    @classmethod
    def from_connector(cls, connector: SearchSourceConnector) -> "LinearWorkspace":
        return cls(
            id=connector.id,
            name=connector.name,
            organization_name=connector.config.get(
                "organization_name", "Linear Workspace"
            ),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "organization_name": self.organization_name,
        }


@dataclass
class LinearIssue:
    """Represents an indexed Linear issue resolved from the knowledge base."""

    id: str
    identifier: str
    title: str
    state: str
    connector_id: int
    document_id: int
    indexed_at: str | None

    @classmethod
    def from_document(cls, document: Document) -> "LinearIssue":
        meta = document.document_metadata or {}
        return cls(
            id=meta.get("issue_id", ""),
            identifier=meta.get("issue_identifier", ""),
            title=meta.get("issue_title", document.title),
            state=meta.get("state", ""),
            connector_id=document.connector_id,
            document_id=document.id,
            indexed_at=meta.get("indexed_at"),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "identifier": self.identifier,
            "title": self.title,
            "state": self.state,
            "connector_id": self.connector_id,
            "document_id": self.document_id,
            "indexed_at": self.indexed_at,
        }


class LinearToolMetadataService:
    """Builds interrupt context for Linear HITL tools.

    All context queries (GraphQL reads) live here.
    Write mutations live in LinearConnector.
    """

    def __init__(self, db_session: AsyncSession):
        self._db_session = db_session

    async def get_creation_context(self, search_space_id: int, user_id: str) -> dict:
        """Return context needed to create a new Linear issue.

        Fetches all teams with their states, members, and labels from the
        Linear API, along with workspace info from the DB connector.

        Returns a dict with keys: workspace, priorities, teams.
        Returns a dict with key 'error' on failure.
        """
        connector = await self._get_linear_connector(search_space_id, user_id)
        if not connector:
            return {"error": "No Linear account connected"}

        workspace = LinearWorkspace.from_connector(connector)
        linear_client = LinearConnector(
            session=self._db_session, connector_id=connector.id
        )

        try:
            priorities = await self._fetch_priority_values(linear_client)
            teams_raw = await self._fetch_teams_context(linear_client)
        except Exception as e:
            return {"error": f"Failed to fetch Linear context: {e!s}"}

        return {
            "workspace": workspace.to_dict(),
            "priorities": priorities,
            "teams": teams_raw,
        }

    async def get_update_context(
        self, search_space_id: int, user_id: str, issue_ref: str
    ) -> dict:
        """Return context needed to update an indexed Linear issue.

        Resolves the issue from the KB (title → identifier → full title),
        then fetches its current state, assignee, labels, and team context
        from the Linear API.

        Returns a dict with keys: workspace, priorities, issue, team.
        Returns a dict with key 'error' if the issue is not found or API fails.
        """
        document = await self._resolve_issue(search_space_id, user_id, issue_ref)
        if not document:
            return {
                "error": f"Issue '{issue_ref}' not found in your indexed Linear issues. "
                "This could mean: (1) the issue doesn't exist, (2) it hasn't been indexed yet, "
                "or (3) the title or identifier is different."
            }

        connector = await self._get_connector_for_document(document, user_id)
        if not connector:
            return {"error": "Connector not found or access denied"}

        workspace = LinearWorkspace.from_connector(connector)
        issue = LinearIssue.from_document(document)

        linear_client = LinearConnector(
            session=self._db_session, connector_id=connector.id
        )

        try:
            priorities = await self._fetch_priority_values(linear_client)
            issue_api = await self._fetch_issue_context(linear_client, issue.id)
        except Exception as e:
            return {"error": f"Failed to fetch Linear issue context: {e!s}"}

        if not issue_api:
            return {
                "error": f"Issue '{issue_ref}' could not be fetched from Linear API"
            }

        team_raw = issue_api.get("team") or {}
        labels_raw = issue_api.get("labels") or {}
        states_raw = team_raw.get("states") or {}
        members_raw = team_raw.get("members") or {}
        team_labels_raw = team_raw.get("labels") or {}

        return {
            "workspace": workspace.to_dict(),
            "priorities": priorities,
            "issue": {
                "id": issue_api.get("id"),
                "identifier": issue_api.get("identifier"),
                "title": issue_api.get("title"),
                "description": issue_api.get("description"),
                "priority": issue_api.get("priority"),
                "url": issue_api.get("url"),
                "current_state": issue_api.get("state"),
                "current_assignee": issue_api.get("assignee"),
                "current_labels": labels_raw.get("nodes", []),
                "team_id": team_raw.get("id"),
                "document_id": issue.document_id,
                "indexed_at": issue.indexed_at,
            },
            "team": {
                "id": team_raw.get("id"),
                "name": team_raw.get("name"),
                "key": team_raw.get("key"),
                "states": states_raw.get("nodes", []),
                "members": members_raw.get("nodes", []),
                "labels": team_labels_raw.get("nodes", []),
            },
        }

    async def get_delete_context(
        self, search_space_id: int, user_id: str, issue_ref: str
    ) -> dict:
        """Return context needed to archive an indexed Linear issue.

        Resolves the issue from the KB only — no Linear API call required.

        Returns a dict with keys: workspace, issue.
        Returns a dict with key 'error' if the issue is not found.
        """
        document = await self._resolve_issue(search_space_id, user_id, issue_ref)
        if not document:
            return {
                "error": f"Issue '{issue_ref}' not found in your indexed Linear issues. "
                "This could mean: (1) the issue doesn't exist, (2) it hasn't been indexed yet, "
                "or (3) the title or identifier is different."
            }

        connector = await self._get_connector_for_document(document, user_id)
        if not connector:
            return {"error": "Connector not found or access denied"}

        workspace = LinearWorkspace.from_connector(connector)
        issue = LinearIssue.from_document(document)

        return {
            "workspace": workspace.to_dict(),
            "issue": {
                **issue.to_dict(),
                "url": f"https://linear.app/issue/{issue.identifier}",
            },
        }

    @staticmethod
    async def _fetch_priority_values(client: LinearConnector) -> list[dict]:
        """Fetch Linear priority values (0-4) with their display labels."""
        query = "{ issuePriorityValues { priority label } }"
        result = await client.execute_graphql_query(query)
        return result.get("data", {}).get("issuePriorityValues", [])

    @staticmethod
    async def _fetch_teams_context(client: LinearConnector) -> list[dict]:
        """Fetch all teams with their states, members, and labels."""
        query = """
        query {
            teams {
                nodes {
                    id name key
                    states { nodes { id name type color position } }
                    members { nodes { id name displayName email avatarUrl active } }
                    labels { nodes { id name color } }
                }
            }
        }
        """
        result = await client.execute_graphql_query(query)
        return result.get("data", {}).get("teams", {}).get("nodes", [])

    @staticmethod
    async def _fetch_issue_context(
        client: LinearConnector, issue_id: str
    ) -> dict | None:
        """Fetch a single issue with its current state, assignee, labels, and team context."""
        query = """
        query LinearIssueContext($id: String!) {
            issue(id: $id) {
                id identifier title description priority url
                state { id name type color }
                assignee { id name displayName email }
                labels { nodes { id name color } }
                team {
                    id name key
                    states { nodes { id name type color position } }
                    members { nodes { id name displayName email avatarUrl active } }
                    labels { nodes { id name color } }
                }
            }
        }
        """
        result = await client.execute_graphql_query(query, {"id": issue_id})
        return result.get("data", {}).get("issue")

    async def _resolve_issue(
        self, search_space_id: int, user_id: str, issue_ref: str
    ) -> Document | None:
        """Resolve an issue from the KB using a 3-step fallback.

        Order: issue_title (most natural) → issue_identifier (e.g. ENG-42) → document.title.
        All comparisons are case-insensitive.
        """
        ref_lower = issue_ref.lower()

        result = await self._db_session.execute(
            select(Document)
            .join(
                SearchSourceConnector, Document.connector_id == SearchSourceConnector.id
            )
            .filter(
                and_(
                    Document.search_space_id == search_space_id,
                    Document.document_type == DocumentType.LINEAR_CONNECTOR,
                    SearchSourceConnector.user_id == user_id,
                    or_(
                        func.lower(
                            cast(Document.document_metadata["issue_title"], String)
                        )
                        == ref_lower,
                        func.lower(
                            cast(Document.document_metadata["issue_identifier"], String)
                        )
                        == ref_lower,
                        func.lower(Document.title) == ref_lower,
                    ),
                )
            )
            .limit(1)
        )
        return result.scalars().first()

    async def _get_linear_connector(
        self, search_space_id: int, user_id: str
    ) -> SearchSourceConnector | None:
        """Fetch the first Linear connector for the given search space and user."""
        result = await self._db_session.execute(
            select(SearchSourceConnector).filter(
                and_(
                    SearchSourceConnector.search_space_id == search_space_id,
                    SearchSourceConnector.user_id == user_id,
                    SearchSourceConnector.connector_type
                    == SearchSourceConnectorType.LINEAR_CONNECTOR,
                )
            )
        )
        return result.scalars().first()

    async def _get_connector_for_document(
        self, document: Document, user_id: str
    ) -> SearchSourceConnector | None:
        """Fetch the connector associated with a document, scoped to the user."""
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
