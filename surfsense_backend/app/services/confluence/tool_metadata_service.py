import logging
from dataclasses import dataclass

from sqlalchemy import and_, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm.attributes import flag_modified

from app.connectors.confluence_history import ConfluenceHistoryConnector
from app.db import (
    Document,
    DocumentType,
    SearchSourceConnector,
    SearchSourceConnectorType,
)

logger = logging.getLogger(__name__)


@dataclass
class ConfluenceWorkspace:
    """Represents a Confluence connector as a workspace for tool context."""

    id: int
    name: str
    base_url: str

    @classmethod
    def from_connector(cls, connector: SearchSourceConnector) -> "ConfluenceWorkspace":
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
class ConfluencePage:
    """Represents an indexed Confluence page resolved from the knowledge base."""

    page_id: str
    page_title: str
    space_id: str
    connector_id: int
    document_id: int
    indexed_at: str | None

    @classmethod
    def from_document(cls, document: Document) -> "ConfluencePage":
        meta = document.document_metadata or {}
        return cls(
            page_id=meta.get("page_id", ""),
            page_title=meta.get("page_title", document.title),
            space_id=meta.get("space_id", ""),
            connector_id=document.connector_id,
            document_id=document.id,
            indexed_at=meta.get("indexed_at"),
        )

    def to_dict(self) -> dict:
        return {
            "page_id": self.page_id,
            "page_title": self.page_title,
            "space_id": self.space_id,
            "connector_id": self.connector_id,
            "document_id": self.document_id,
            "indexed_at": self.indexed_at,
        }


class ConfluenceToolMetadataService:
    """Builds interrupt context for Confluence HITL tools."""

    def __init__(self, db_session: AsyncSession):
        self._db_session = db_session

    async def _check_account_health(self, connector: SearchSourceConnector) -> bool:
        """Check if the Confluence connector auth is still valid.

        Returns True if auth is expired/invalid, False if healthy.
        """
        try:
            client = ConfluenceHistoryConnector(
                session=self._db_session, connector_id=connector.id
            )
            await client._get_valid_token()
            await client.close()
            return False
        except Exception as e:
            logger.warning(
                "Confluence connector %s health check failed: %s", connector.id, e
            )
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
        """Return context needed to create a new Confluence page.

        Fetches all connected accounts, and for the first healthy one fetches spaces.
        """
        connectors = await self._get_all_confluence_connectors(search_space_id, user_id)
        if not connectors:
            return {"error": "No Confluence account connected"}

        accounts = []
        spaces = []
        fetched_context = False

        for connector in connectors:
            auth_expired = await self._check_account_health(connector)
            workspace = ConfluenceWorkspace.from_connector(connector)
            accounts.append(
                {
                    **workspace.to_dict(),
                    "auth_expired": auth_expired,
                }
            )

            if not auth_expired and not fetched_context:
                try:
                    client = ConfluenceHistoryConnector(
                        session=self._db_session, connector_id=connector.id
                    )
                    raw_spaces = await client.get_all_spaces()
                    spaces = [
                        {"id": s.get("id"), "key": s.get("key"), "name": s.get("name")}
                        for s in raw_spaces
                    ]
                    await client.close()
                    fetched_context = True
                except Exception as e:
                    logger.warning(
                        "Failed to fetch Confluence spaces for connector %s: %s",
                        connector.id,
                        e,
                    )

        return {
            "accounts": accounts,
            "spaces": spaces,
        }

    async def get_update_context(
        self, search_space_id: int, user_id: str, page_ref: str
    ) -> dict:
        """Return context needed to update an indexed Confluence page.

        Resolves the page from KB, then fetches current content and version from API.
        """
        document = await self._resolve_page(search_space_id, user_id, page_ref)
        if not document:
            return {
                "error": f"Page '{page_ref}' not found in your synced Confluence pages. "
                "Please make sure the page is indexed in your knowledge base."
            }

        connector = await self._get_connector_for_document(document, user_id)
        if not connector:
            return {"error": "Connector not found or access denied"}

        auth_expired = await self._check_account_health(connector)
        if auth_expired:
            return {
                "error": "Confluence authentication has expired. Please re-authenticate.",
                "auth_expired": True,
                "connector_id": connector.id,
            }

        workspace = ConfluenceWorkspace.from_connector(connector)
        page = ConfluencePage.from_document(document)

        try:
            client = ConfluenceHistoryConnector(
                session=self._db_session, connector_id=connector.id
            )
            page_data = await client.get_page(page.page_id)
            await client.close()
        except Exception as e:
            error_str = str(e).lower()
            if (
                "401" in error_str
                or "403" in error_str
                or "authentication" in error_str
            ):
                return {
                    "error": f"Failed to fetch Confluence page: {e!s}",
                    "auth_expired": True,
                    "connector_id": connector.id,
                }
            return {"error": f"Failed to fetch Confluence page: {e!s}"}

        body_storage = ""
        body_obj = page_data.get("body", {})
        if isinstance(body_obj, dict):
            storage = body_obj.get("storage", {})
            if isinstance(storage, dict):
                body_storage = storage.get("value", "")

        version_obj = page_data.get("version", {})
        version_number = (
            version_obj.get("number", 1) if isinstance(version_obj, dict) else 1
        )

        return {
            "account": {**workspace.to_dict(), "auth_expired": False},
            "page": {
                "page_id": page.page_id,
                "page_title": page_data.get("title", page.page_title),
                "space_id": page.space_id,
                "body": body_storage,
                "version": version_number,
                "document_id": page.document_id,
                "indexed_at": page.indexed_at,
            },
        }

    async def get_deletion_context(
        self, search_space_id: int, user_id: str, page_ref: str
    ) -> dict:
        """Return context needed to delete a Confluence page (KB metadata only)."""
        document = await self._resolve_page(search_space_id, user_id, page_ref)
        if not document:
            return {
                "error": f"Page '{page_ref}' not found in your synced Confluence pages. "
                "Please make sure the page is indexed in your knowledge base."
            }

        connector = await self._get_connector_for_document(document, user_id)
        if not connector:
            return {"error": "Connector not found or access denied"}

        auth_expired = connector.config.get("auth_expired", False)
        workspace = ConfluenceWorkspace.from_connector(connector)
        page = ConfluencePage.from_document(document)

        return {
            "account": {**workspace.to_dict(), "auth_expired": auth_expired},
            "page": page.to_dict(),
        }

    async def _resolve_page(
        self, search_space_id: int, user_id: str, page_ref: str
    ) -> Document | None:
        """Resolve a page from KB: page_title -> document.title."""
        ref_lower = page_ref.lower()

        result = await self._db_session.execute(
            select(Document)
            .join(
                SearchSourceConnector, Document.connector_id == SearchSourceConnector.id
            )
            .filter(
                and_(
                    Document.search_space_id == search_space_id,
                    Document.document_type == DocumentType.CONFLUENCE_CONNECTOR,
                    SearchSourceConnector.user_id == user_id,
                    or_(
                        func.lower(Document.document_metadata.op("->>")("page_title"))
                        == ref_lower,
                        func.lower(Document.title) == ref_lower,
                    ),
                )
            )
            .order_by(Document.updated_at.desc().nullslast())
            .limit(1)
        )
        return result.scalars().first()

    async def _get_all_confluence_connectors(
        self, search_space_id: int, user_id: str
    ) -> list[SearchSourceConnector]:
        result = await self._db_session.execute(
            select(SearchSourceConnector).filter(
                and_(
                    SearchSourceConnector.search_space_id == search_space_id,
                    SearchSourceConnector.user_id == user_id,
                    SearchSourceConnector.connector_type
                    == SearchSourceConnectorType.CONFLUENCE_CONNECTOR,
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
