"""Google Drive API client."""

from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.ext.asyncio import AsyncSession

from .credentials import get_valid_credentials


class GoogleDriveClient:
    """Client for Google Drive API operations."""

    def __init__(self, session: AsyncSession, connector_id: int):
        """
        Initialize Google Drive client.

        Args:
            session: Database session
            connector_id: ID of the Drive connector
        """
        self.session = session
        self.connector_id = connector_id
        self.service = None

    async def get_service(self):
        """
        Get or create the Drive service instance.

        Returns:
            Google Drive service instance

        Raises:
            Exception: If service creation fails
        """
        if self.service:
            return self.service

        try:
            credentials = await get_valid_credentials(self.session, self.connector_id)
            self.service = build("drive", "v3", credentials=credentials)
            return self.service
        except Exception as e:
            raise Exception(f"Failed to create Google Drive service: {e!s}") from e

    async def list_files(
        self,
        query: str = "",
        fields: str = "nextPageToken, files(id, name, mimeType, modifiedTime, md5Checksum, size, webViewLink, parents, owners, createdTime, description)",
        page_size: int = 100,
        page_token: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None, str | None]:
        """
        List files from Google Drive with pagination.

        Args:
            query: Search query (e.g., "mimeType != 'application/vnd.google-apps.folder'")
            fields: Fields to retrieve
            page_size: Number of files per page (max 1000)
            page_token: Token for next page

        Returns:
            Tuple of (files list, next_page_token, error message)
        """
        try:
            service = await self.get_service()

            params = {
                "pageSize": min(page_size, 1000),
                "fields": fields,
                "supportsAllDrives": True,
                "includeItemsFromAllDrives": True,
            }

            if query:
                params["q"] = query
            if page_token:
                params["pageToken"] = page_token

            result = service.files().list(**params).execute()

            files = result.get("files", [])
            next_token = result.get("nextPageToken")

            return files, next_token, None

        except HttpError as e:
            error_msg = f"HTTP error listing files: {e.resp.status} - {e.error_details}"
            return [], None, error_msg
        except Exception as e:
            return [], None, f"Error listing files: {e!s}"

    async def get_file_metadata(
        self, file_id: str, fields: str = "*"
    ) -> tuple[dict[str, Any] | None, str | None]:
        """
        Get metadata for a specific file.

        Args:
            file_id: ID of the file
            fields: Fields to retrieve

        Returns:
            Tuple of (file metadata, error message)
        """
        try:
            service = await self.get_service()
            file = (
                service.files()
                .get(fileId=file_id, fields=fields, supportsAllDrives=True)
                .execute()
            )
            return file, None
        except HttpError as e:
            return None, f"HTTP error getting file metadata: {e.resp.status}"
        except Exception as e:
            return None, f"Error getting file metadata: {e!s}"

    async def download_file(self, file_id: str) -> tuple[bytes | None, str | None]:
        """
        Download binary file content.

        Args:
            file_id: ID of the file to download

        Returns:
            Tuple of (file content bytes, error message)
        """
        try:
            service = await self.get_service()
            request = service.files().get_media(fileId=file_id)

            import io

            fh = io.BytesIO()
            from googleapiclient.http import MediaIoBaseDownload

            downloader = MediaIoBaseDownload(fh, request)

            done = False
            while not done:
                _, done = downloader.next_chunk()

            return fh.getvalue(), None

        except HttpError as e:
            return None, f"HTTP error downloading file: {e.resp.status}"
        except Exception as e:
            return None, f"Error downloading file: {e!s}"

    async def export_google_file(
        self, file_id: str, mime_type: str
    ) -> tuple[bytes | None, str | None]:
        """
        Export Google Workspace file to specified format.

        Args:
            file_id: ID of the Google file
            mime_type: Target MIME type (e.g., 'application/pdf', 'text/plain')

        Returns:
            Tuple of (exported content as bytes, error message)
        """
        try:
            service = await self.get_service()
            content = (
                service.files().export(fileId=file_id, mimeType=mime_type).execute()
            )

            # Content is already bytes from the API
            # Keep as bytes to support both text and binary formats (like PDF)
            if not isinstance(content, bytes):
                content = content.encode("utf-8")

            return content, None

        except HttpError as e:
            return None, f"HTTP error exporting file: {e.resp.status}"
        except Exception as e:
            return None, f"Error exporting file: {e!s}"
