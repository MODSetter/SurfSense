from dataclasses import dataclass

from sqlalchemy import and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import (
    Document,
    DocumentType,
    SearchSourceConnector,
    SearchSourceConnectorType,
)


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
                "total_pages_per_account": {},
                "error": "No Notion accounts connected",
            }

        parent_pages = await self._get_parent_pages_by_account(search_space_id, accounts)
        page_counts = await self._get_page_counts_by_account(search_space_id, accounts)

        return {
            "accounts": [acc.to_dict() for acc in accounts],
            "parent_pages": parent_pages,
            "total_pages_per_account": page_counts,
        }

    async def get_update_context(
        self, search_space_id: int, user_id: str, page_id: str
    ) -> dict:
        result = await self._db_session.execute(
            select(Document).filter(
                and_(
                    Document.search_space_id == search_space_id,
                    Document.document_type == DocumentType.NOTION_CONNECTOR,
                    Document.document_metadata["page_id"].astext == page_id,
                )
            )
        )
        document = result.scalars().first()

        if not document:
            return {"error": f"Page {page_id} not found in indexed documents"}

        if not document.connector_id:
            return {"error": "Document has no associated connector"}

        result = await self._db_session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == document.connector_id
            )
        )
        connector = result.scalars().first()

        if not connector:
            return {"error": "Connector not found"}

        account = NotionAccount.from_connector(connector)

        return {
            "account": account.to_dict(),
            "page_id": page_id,
            "current_title": document.title,
            "current_content": document.content,
            "document_id": document.id,
            "indexed_at": document.document_metadata.get("indexed_at"),
        }

    async def get_delete_context(
        self, search_space_id: int, user_id: str, page_id: str
    ) -> dict:
        return await self.get_update_context(search_space_id, user_id, page_id)

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
            ]

        return parent_pages

    async def _get_page_counts_by_account(
        self, search_space_id: int, accounts: list[NotionAccount]
    ) -> dict:
        counts = {}

        for account in accounts:
            result = await self._db_session.execute(
                select(func.count(Document.id)).filter(
                    and_(
                        Document.search_space_id == search_space_id,
                        Document.connector_id == account.id,
                        Document.document_type == DocumentType.NOTION_CONNECTOR,
                    )
                )
            )
            count = result.scalar()
            counts[account.id] = count

        return counts
