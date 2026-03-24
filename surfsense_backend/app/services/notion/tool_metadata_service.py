import logging
from dataclasses import dataclass

from sqlalchemy import and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm.attributes import flag_modified

from app.connectors.notion_history import NotionHistoryConnector
from app.db import (
    Document,
    DocumentType,
    SearchSourceConnector,
    SearchSourceConnectorType,
)

logger = logging.getLogger(__name__)


@dataclass
class NotionAccount:
    id: int
    name: str
    workspace_id: str | None
    workspace_name: str
    workspace_icon: str

    @classmethod
    def from_connector(cls, connector: SearchSourceConnector) -> "NotionAccount":
        return cls(
            id=connector.id,
            name=connector.name,
            workspace_id=connector.config.get("workspace_id"),
            workspace_name=connector.config.get("workspace_name", "Unnamed Workspace"),
            workspace_icon=connector.config.get("workspace_icon", "📄"),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "workspace_id": self.workspace_id,
            "workspace_name": self.workspace_name,
            "workspace_icon": self.workspace_icon,
        }


@dataclass
class NotionPage:
    page_id: str
    title: str
    connector_id: int
    document_id: int

    @classmethod
    def from_document(cls, document: Document) -> "NotionPage":
        return cls(
            page_id=document.document_metadata.get("page_id"),
            title=document.title,
            connector_id=document.connector_id,
            document_id=document.id,
        )

    def to_dict(self) -> dict:
        return {
            "page_id": self.page_id,
            "title": self.title,
            "connector_id": self.connector_id,
            "document_id": self.document_id,
        }


class NotionToolMetadataService:
    def __init__(self, db_session: AsyncSession):
        self._db_session = db_session

    async def get_creation_context(self, search_space_id: int, user_id: str) -> dict:
        accounts = await self._get_notion_accounts(search_space_id, user_id)

        if not accounts:
            return {
                "accounts": [],
                "parent_pages": {},
                "error": "No Notion accounts connected",
            }

        parent_pages = await self._get_parent_pages_by_account(
            search_space_id, accounts
        )

        accounts_with_status = []
        for acc in accounts:
            acc_dict = acc.to_dict()
            auth_expired = await self._check_account_health(acc.id)
            acc_dict["auth_expired"] = auth_expired
            if auth_expired:
                try:
                    result = await self._db_session.execute(
                        select(SearchSourceConnector).where(
                            SearchSourceConnector.id == acc.id
                        )
                    )
                    db_connector = result.scalar_one_or_none()
                    if db_connector and not db_connector.config.get("auth_expired"):
                        db_connector.config = {
                            **db_connector.config,
                            "auth_expired": True,
                        }
                        flag_modified(db_connector, "config")
                        await self._db_session.commit()
                        await self._db_session.refresh(db_connector)
                except Exception:
                    logger.warning(
                        "Failed to persist auth_expired for connector %s",
                        acc.id,
                        exc_info=True,
                    )
            accounts_with_status.append(acc_dict)

        return {
            "accounts": accounts_with_status,
            "parent_pages": parent_pages,
        }

    async def get_update_context(
        self, search_space_id: int, user_id: str, page_title: str
    ) -> dict:
        result = await self._db_session.execute(
            select(Document)
            .join(
                SearchSourceConnector, Document.connector_id == SearchSourceConnector.id
            )
            .filter(
                and_(
                    Document.search_space_id == search_space_id,
                    Document.document_type == DocumentType.NOTION_CONNECTOR,
                    func.lower(Document.title) == func.lower(page_title),
                    SearchSourceConnector.user_id == user_id,
                )
            )
            .order_by(Document.updated_at.desc().nullslast())
            .limit(1)
        )
        document = result.scalars().first()

        if not document:
            return {
                "error": f"Page '{page_title}' not found in your synced Notion pages. "
                "This could mean: (1) the page doesn't exist, (2) it hasn't been synced yet, "
                "or (3) the page title is different. Please check the exact page title in Notion."
            }

        if not document.connector_id:
            return {"error": "Document has no associated connector"}

        result = await self._db_session.execute(
            select(SearchSourceConnector).filter(
                and_(
                    SearchSourceConnector.id == document.connector_id,
                    SearchSourceConnector.user_id == user_id,
                )
            )
        )
        connector = result.scalars().first()

        if not connector:
            return {"error": "Connector not found or access denied"}

        account = NotionAccount.from_connector(connector)

        page_id = document.document_metadata.get("page_id")
        if not page_id:
            return {"error": "Page ID not found in document metadata"}

        current_title = document.title
        document_id = document.id
        indexed_at = document.document_metadata.get("indexed_at")

        acc_dict = account.to_dict()
        auth_expired = await self._check_account_health(connector.id)
        acc_dict["auth_expired"] = auth_expired
        if auth_expired:
            try:
                if not connector.config.get("auth_expired"):
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

        return {
            "account": acc_dict,
            "page_id": page_id,
            "current_title": current_title,
            "document_id": document_id,
            "indexed_at": indexed_at,
        }

    async def get_delete_context(
        self, search_space_id: int, user_id: str, page_title: str
    ) -> dict:
        return await self.get_update_context(search_space_id, user_id, page_title)

    async def _get_notion_accounts(
        self, search_space_id: int, user_id: str
    ) -> list[NotionAccount]:
        result = await self._db_session.execute(
            select(SearchSourceConnector)
            .filter(
                and_(
                    SearchSourceConnector.search_space_id == search_space_id,
                    SearchSourceConnector.user_id == user_id,
                    SearchSourceConnector.connector_type
                    == SearchSourceConnectorType.NOTION_CONNECTOR,
                )
            )
            .order_by(SearchSourceConnector.last_indexed_at.desc())
        )
        connectors = result.scalars().all()
        return [NotionAccount.from_connector(conn) for conn in connectors]

    async def _check_account_health(self, connector_id: int) -> bool:
        """Check if a Notion connector's token is still valid.

        Uses a lightweight ``users.me()`` call to verify the token.

        Returns True if the token is expired/invalid, False if healthy.
        """
        try:
            connector = NotionHistoryConnector(
                session=self._db_session, connector_id=connector_id
            )
            client = await connector._get_client()
            await client.users.me()
            return False
        except Exception as e:
            logger.warning(
                "Notion connector %s health check failed: %s", connector_id, e
            )
            return True

    async def _get_parent_pages_by_account(
        self, search_space_id: int, accounts: list[NotionAccount]
    ) -> dict:
        parent_pages = {}

        for account in accounts:
            result = await self._db_session.execute(
                select(Document)
                .filter(
                    and_(
                        Document.search_space_id == search_space_id,
                        Document.connector_id == account.id,
                        Document.document_type == DocumentType.NOTION_CONNECTOR,
                    )
                )
                .order_by(Document.updated_at.desc())
                .limit(50)
            )
            documents = result.scalars().all()

            parent_pages[account.id] = [
                {
                    "page_id": doc.document_metadata.get("page_id"),
                    "title": doc.title,
                    "document_id": doc.id,
                }
                for doc in documents
                if doc.document_metadata.get("page_id")
            ]

        return parent_pages
