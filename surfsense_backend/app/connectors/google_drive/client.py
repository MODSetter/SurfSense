"""Google Drive API client."""

import asyncio
import io
import logging
import threading
import time
from typing import Any

import httplib2
from google.oauth2.credentials import Credentials
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload
from sqlalchemy.ext.asyncio import AsyncSession

from .credentials import get_valid_credentials
from .file_types import GOOGLE_DOC, GOOGLE_SHEET

logger = logging.getLogger(__name__)


def _build_thread_http(credentials: Credentials) -> AuthorizedHttp:
    """Create a per-thread HTTP transport so concurrent downloads don't share
    the same ``httplib2.Http`` (which is not thread-safe)."""
    return AuthorizedHttp(credentials, http=httplib2.Http())


class GoogleDriveClient:
    """Client for Google Drive API operations."""

    def __init__(
        self,
        session: AsyncSession,
        connector_id: int,
        credentials: "Credentials | None" = None,
    ):
        """
        Initialize Google Drive client.

        Args:
            session: Database session
            connector_id: ID of the Drive connector
            credentials: Pre-built credentials (e.g. from Composio). If None,
                         credentials are loaded from the DB connector config.
        """
        self.session = session
        self.connector_id = connector_id
        self._credentials = credentials
        self._resolved_credentials: Credentials | None = None
        self.service = None
        self._service_lock = asyncio.Lock()

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

        async with self._service_lock:
            if self.service:
                return self.service

            try:
                if self._credentials:
                    credentials = self._credentials
                else:
                    credentials = await get_valid_credentials(
                        self.session, self.connector_id
                    )
                self._resolved_credentials = credentials
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

    @staticmethod
    def _sync_download_file(
        service, file_id: str, credentials: Credentials,
    ) -> tuple[bytes | None, str | None]:
        """Blocking download — runs on a worker thread via ``to_thread``."""
        thread = threading.current_thread().name
        t0 = time.monotonic()
        logger.info(f"[download] START file={file_id} thread={thread}")
        try:
            from googleapiclient.http import MediaIoBaseDownload

            http = _build_thread_http(credentials)
            request = service.files().get_media(fileId=file_id)
            request.http = http
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            return fh.getvalue(), None
        except HttpError as e:
            return None, f"HTTP error downloading file: {e.resp.status}"
        except Exception as e:
            return None, f"Error downloading file: {e!s}"
        finally:
            logger.info(f"[download] END file={file_id} thread={thread} elapsed={time.monotonic() - t0:.2f}s")

    async def download_file(self, file_id: str) -> tuple[bytes | None, str | None]:
        """
        Download binary file content.

        Args:
            file_id: ID of the file to download

        Returns:
            Tuple of (file content bytes, error message)
        """
        service = await self.get_service()
        return await asyncio.to_thread(
            self._sync_download_file, service, file_id, self._resolved_credentials,
        )

    @staticmethod
    def _sync_download_file_to_disk(
        service, file_id: str, dest_path: str, chunksize: int,
        credentials: Credentials,
    ) -> str | None:
        """Blocking download-to-disk — runs on a worker thread via ``to_thread``."""
        thread = threading.current_thread().name
        t0 = time.monotonic()
        logger.info(f"[download-to-disk] START file={file_id} thread={thread}")
        try:
            from googleapiclient.http import MediaIoBaseDownload

            http = _build_thread_http(credentials)
            request = service.files().get_media(fileId=file_id)
            request.http = http
            with open(dest_path, "wb") as fh:
                downloader = MediaIoBaseDownload(fh, request, chunksize=chunksize)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
            return None
        except HttpError as e:
            return f"HTTP error downloading file: {e.resp.status}"
        except Exception as e:
            return f"Error downloading file: {e!s}"
        finally:
            logger.info(f"[download-to-disk] END file={file_id} thread={thread} elapsed={time.monotonic() - t0:.2f}s")

    async def download_file_to_disk(
        self, file_id: str, dest_path: str, chunksize: int = 5 * 1024 * 1024,
    ) -> str | None:
        """Stream file directly to disk in chunks, avoiding full in-memory buffering.

        Returns error message on failure, None on success.
        """
        service = await self.get_service()
        return await asyncio.to_thread(
            self._sync_download_file_to_disk,
            service, file_id, dest_path, chunksize, self._resolved_credentials,
        )

    @staticmethod
    def _sync_export_google_file(
        service, file_id: str, mime_type: str, credentials: Credentials,
    ) -> tuple[bytes | None, str | None]:
        """Blocking export — runs on a worker thread via ``to_thread``."""
        thread = threading.current_thread().name
        t0 = time.monotonic()
        logger.info(f"[export] START file={file_id} thread={thread}")
        try:
            http = _build_thread_http(credentials)
            content = (
                service.files()
                .export(fileId=file_id, mimeType=mime_type)
                .execute(http=http)
            )
            if not isinstance(content, bytes):
                content = content.encode("utf-8")
            return content, None
        except HttpError as e:
            return None, f"HTTP error exporting file: {e.resp.status}"
        except Exception as e:
            return None, f"Error exporting file: {e!s}"
        finally:
            logger.info(f"[export] END file={file_id} thread={thread} elapsed={time.monotonic() - t0:.2f}s")

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
        service = await self.get_service()
        return await asyncio.to_thread(
            self._sync_export_google_file, service, file_id, mime_type,
            self._resolved_credentials,
        )

    async def create_file(
        self,
        name: str,
        mime_type: str,
        parent_folder_id: str | None = None,
        content: str | None = None,
    ) -> dict[str, Any]:
        service = await self.get_service()

        body: dict[str, Any] = {"name": name, "mimeType": mime_type}
        if parent_folder_id:
            body["parents"] = [parent_folder_id]

        media: MediaIoBaseUpload | None = None
        if content:
            if mime_type == GOOGLE_DOC:
                import markdown as md_lib

                html = md_lib.markdown(content)
                media = MediaIoBaseUpload(
                    io.BytesIO(html.encode("utf-8")),
                    mimetype="text/html",
                    resumable=False,
                )
            elif mime_type == GOOGLE_SHEET:
                media = MediaIoBaseUpload(
                    io.BytesIO(content.encode("utf-8")),
                    mimetype="text/csv",
                    resumable=False,
                )

        if media:
            return (
                service.files()
                .create(
                    body=body,
                    media_body=media,
                    fields="id,name,mimeType,webViewLink",
                    supportsAllDrives=True,
                )
                .execute()
            )

        return (
            service.files()
            .create(
                body=body,
                fields="id,name,mimeType,webViewLink",
                supportsAllDrives=True,
            )
            .execute()
        )

    async def trash_file(self, file_id: str) -> bool:
        service = await self.get_service()
        service.files().update(
            fileId=file_id,
            body={"trashed": True},
            supportsAllDrives=True,
        ).execute()
        return True
