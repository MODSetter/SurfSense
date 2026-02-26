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
class GoogleDriveAccount:
    id: int
    name: str

    @classmethod
    def from_connector(cls, connector: SearchSourceConnector) -> "GoogleDriveAccount":
        return cls(id=connector.id, name=connector.name)

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name}


@dataclass
class GoogleDriveFile:
    file_id: str
    name: str
    mime_type: str
    web_view_link: str
    connector_id: int
    document_id: int

    @classmethod
    def from_document(cls, document: Document) -> "GoogleDriveFile":
        meta = document.document_metadata or {}
        return cls(
            file_id=meta.get("google_drive_file_id", ""),
            name=meta.get("google_drive_file_name", document.title),
            mime_type=meta.get("google_drive_mime_type", ""),
            web_view_link=meta.get("web_view_link", ""),
            connector_id=document.connector_id,
            document_id=document.id,
        )

    def to_dict(self) -> dict:
        return {
            "file_id": self.file_id,
            "name": self.name,
            "mime_type": self.mime_type,
            "web_view_link": self.web_view_link,
            "connector_id": self.connector_id,
            "document_id": self.document_id,
        }


class GoogleDriveToolMetadataService:
    def __init__(self, db_session: AsyncSession):
        self._db_session = db_session

    async def get_creation_context(self, search_space_id: int, user_id: str) -> dict:
        accounts = await self._get_google_drive_accounts(search_space_id, user_id)

        if not accounts:
            return {
                "accounts": [],
                "supported_types": [],
                "error": "No Google Drive account connected",
            }

        return {
            "accounts": [acc.to_dict() for acc in accounts],
            "supported_types": ["google_doc", "google_sheet"],
        }

    async def get_trash_context(
        self, search_space_id: int, user_id: str, file_name: str
    ) -> dict:
        result = await self._db_session.execute(
            select(Document)
            .join(
                SearchSourceConnector, Document.connector_id == SearchSourceConnector.id
            )
            .filter(
                and_(
                    Document.search_space_id == search_space_id,
                    Document.document_type == DocumentType.GOOGLE_DRIVE_FILE,
                    func.lower(Document.title) == func.lower(file_name),
                    SearchSourceConnector.user_id == user_id,
                )
            )
        )
        document = result.scalars().first()

        if not document:
            return {
                "error": (
                    f"File '{file_name}' not found in your indexed Google Drive files. "
                    "This could mean: (1) the file doesn't exist, (2) it hasn't been indexed yet, "
                    "or (3) the file name is different."
                )
            }

        if not document.connector_id:
            return {"error": "Document has no associated connector"}

        result = await self._db_session.execute(
            select(SearchSourceConnector).filter(
                and_(
                    SearchSourceConnector.id == document.connector_id,
                    SearchSourceConnector.user_id == user_id,
                    SearchSourceConnector.connector_type
                    == SearchSourceConnectorType.GOOGLE_DRIVE_CONNECTOR,
                )
            )
        )
        connector = result.scalars().first()

        if not connector:
            return {"error": "Connector not found or access denied"}

        account = GoogleDriveAccount.from_connector(connector)
        file = GoogleDriveFile.from_document(document)

        return {
            "account": account.to_dict(),
            "file": file.to_dict(),
        }

    async def _get_google_drive_accounts(
        self, search_space_id: int, user_id: str
    ) -> list[GoogleDriveAccount]:
        result = await self._db_session.execute(
            select(SearchSourceConnector)
            .filter(
                and_(
                    SearchSourceConnector.search_space_id == search_space_id,
                    SearchSourceConnector.user_id == user_id,
                    SearchSourceConnector.connector_type
                    == SearchSourceConnectorType.GOOGLE_DRIVE_CONNECTOR,
                )
            )
            .order_by(SearchSourceConnector.last_indexed_at.desc())
        )
        connectors = result.scalars().all()
        return [GoogleDriveAccount.from_connector(c) for c in connectors]
