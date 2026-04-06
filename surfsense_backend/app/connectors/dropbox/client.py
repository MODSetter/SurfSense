"""Dropbox API client using Dropbox HTTP API v2."""

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm.attributes import flag_modified

from app.config import config
from app.db import SearchSourceConnector
from app.utils.oauth_security import TokenEncryption

logger = logging.getLogger(__name__)

API_BASE = "https://api.dropboxapi.com"
CONTENT_BASE = "https://content.dropboxapi.com"
TOKEN_URL = "https://api.dropboxapi.com/oauth2/token"


class DropboxClient:
    """Client for Dropbox via the HTTP API v2."""

    def __init__(self, session: AsyncSession, connector_id: int):
        self._session = session
        self._connector_id = connector_id

    async def _get_valid_token(self) -> str:
        result = await self._session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == self._connector_id
            )
        )
        connector = result.scalars().first()
        if not connector:
            raise ValueError(f"Connector {self._connector_id} not found")

        cfg = connector.config or {}
        is_encrypted = cfg.get("_token_encrypted", False)
        token_encryption = (
            TokenEncryption(config.SECRET_KEY) if config.SECRET_KEY else None
        )

        access_token = cfg.get("access_token", "")
        refresh_token = cfg.get("refresh_token")

        if is_encrypted and token_encryption:
            if access_token:
                access_token = token_encryption.decrypt_token(access_token)
            if refresh_token:
                refresh_token = token_encryption.decrypt_token(refresh_token)

        expires_at_str = cfg.get("expires_at")
        is_expired = False
        if expires_at_str:
            expires_at = datetime.fromisoformat(expires_at_str)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            is_expired = expires_at <= datetime.now(UTC)

        if not is_expired and access_token:
            return access_token

        if not refresh_token:
            cfg["auth_expired"] = True
            connector.config = cfg
            flag_modified(connector, "config")
            await self._session.commit()
            raise ValueError("Dropbox token expired and no refresh token available")

        token_data = await self._refresh_token(refresh_token)

        new_access = token_data["access_token"]
        expires_in = token_data.get("expires_in")

        new_expires_at = None
        if expires_in:
            new_expires_at = datetime.now(UTC) + timedelta(seconds=int(expires_in))

        if token_encryption:
            cfg["access_token"] = token_encryption.encrypt_token(new_access)
        else:
            cfg["access_token"] = new_access

        cfg["expires_at"] = new_expires_at.isoformat() if new_expires_at else None
        cfg["expires_in"] = expires_in
        cfg["_token_encrypted"] = bool(token_encryption)
        cfg.pop("auth_expired", None)

        connector.config = cfg
        flag_modified(connector, "config")
        await self._session.commit()

        return new_access

    async def _refresh_token(self, refresh_token: str) -> dict:
        data = {
            "client_id": config.DROPBOX_APP_KEY,
            "client_secret": config.DROPBOX_APP_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30.0,
            )
        if resp.status_code != 200:
            error_detail = resp.text
            try:
                error_json = resp.json()
                error_detail = error_json.get("error_description", error_detail)
            except Exception:
                pass
            raise ValueError(f"Dropbox token refresh failed: {error_detail}")
        return resp.json()

    async def _request(
        self, path: str, json_body: dict | None = None, **kwargs
    ) -> httpx.Response:
        """Make an authenticated RPC request to the Dropbox API."""
        token = await self._get_valid_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{API_BASE}{path}",
                headers=headers,
                json=json_body,
                timeout=60.0,
                **kwargs,
            )

        if resp.status_code == 401:
            result = await self._session.execute(
                select(SearchSourceConnector).filter(
                    SearchSourceConnector.id == self._connector_id
                )
            )
            connector = result.scalars().first()
            if connector:
                cfg = connector.config or {}
                cfg["auth_expired"] = True
                connector.config = cfg
                flag_modified(connector, "config")
                await self._session.commit()
            raise ValueError("Dropbox authentication expired (401)")

        return resp

    async def _content_request(
        self, path: str, api_arg: dict, content: bytes | None = None, **kwargs
    ) -> httpx.Response:
        """Make an authenticated content-upload/download request."""
        token = await self._get_valid_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Dropbox-API-Arg": json.dumps(api_arg),
            "Content-Type": "application/octet-stream",
        }
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{CONTENT_BASE}{path}",
                headers=headers,
                content=content or b"",
                timeout=120.0,
                **kwargs,
            )

        if resp.status_code == 401:
            result = await self._session.execute(
                select(SearchSourceConnector).filter(
                    SearchSourceConnector.id == self._connector_id
                )
            )
            connector = result.scalars().first()
            if connector:
                cfg = connector.config or {}
                cfg["auth_expired"] = True
                connector.config = cfg
                flag_modified(connector, "config")
                await self._session.commit()
            raise ValueError("Dropbox authentication expired (401)")

        return resp

    async def list_folder(
        self, path: str = ""
    ) -> tuple[list[dict[str, Any]], str | None]:
        """List all items in a folder. Handles pagination via cursor."""
        all_items: list[dict[str, Any]] = []

        resp = await self._request(
            "/2/files/list_folder",
            {"path": path, "recursive": False, "include_non_downloadable_files": True},
        )
        if resp.status_code != 200:
            return [], f"Failed to list folder: {resp.status_code} - {resp.text}"

        data = resp.json()
        all_items.extend(data.get("entries", []))

        while data.get("has_more"):
            cursor = data["cursor"]
            resp = await self._request(
                "/2/files/list_folder/continue", {"cursor": cursor}
            )
            if resp.status_code != 200:
                return all_items, f"Pagination failed: {resp.status_code}"
            data = resp.json()
            all_items.extend(data.get("entries", []))

        return all_items, None

    async def get_latest_cursor(
        self, path: str = ""
    ) -> tuple[str | None, str | None]:
        """Get a cursor representing the current state of a folder.

        Uses /2/files/list_folder/get_latest_cursor so we can later call
        get_changes to receive only incremental updates.
        """
        resp = await self._request(
            "/2/files/list_folder/get_latest_cursor",
            {"path": path, "recursive": False, "include_non_downloadable_files": True},
        )
        if resp.status_code != 200:
            return None, f"Failed to get cursor: {resp.status_code} - {resp.text}"
        return resp.json().get("cursor"), None

    async def get_changes(
        self, cursor: str
    ) -> tuple[list[dict[str, Any]], str | None, str | None]:
        """Fetch incremental changes since the given cursor.

        Calls /2/files/list_folder/continue and handles pagination.
        Returns (entries, new_cursor, error).
        """
        all_entries: list[dict[str, Any]] = []

        resp = await self._request(
            "/2/files/list_folder/continue", {"cursor": cursor}
        )
        if resp.status_code == 401:
            return [], None, "Dropbox authentication expired (401)"
        if resp.status_code != 200:
            return [], None, f"Failed to get changes: {resp.status_code} - {resp.text}"

        data = resp.json()
        all_entries.extend(data.get("entries", []))

        while data.get("has_more"):
            cursor = data["cursor"]
            resp = await self._request(
                "/2/files/list_folder/continue", {"cursor": cursor}
            )
            if resp.status_code != 200:
                return all_entries, data.get("cursor"), f"Pagination failed: {resp.status_code}"
            data = resp.json()
            all_entries.extend(data.get("entries", []))

        return all_entries, data.get("cursor"), None

    async def get_metadata(self, path: str) -> tuple[dict[str, Any] | None, str | None]:
        resp = await self._request("/2/files/get_metadata", {"path": path})
        if resp.status_code != 200:
            return None, f"Failed to get metadata: {resp.status_code} - {resp.text}"
        return resp.json(), None

    async def download_file(self, path: str) -> tuple[bytes | None, str | None]:
        resp = await self._content_request("/2/files/download", {"path": path})
        if resp.status_code != 200:
            return None, f"Download failed: {resp.status_code}"
        return resp.content, None

    async def download_file_to_disk(self, path: str, dest_path: str) -> str | None:
        """Stream file content to disk. Returns error message on failure."""
        token = await self._get_valid_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Dropbox-API-Arg": json.dumps({"path": path}),
        }
        async with (
            httpx.AsyncClient() as client,
            client.stream(
                "POST",
                f"{CONTENT_BASE}/2/files/download",
                headers=headers,
                timeout=120.0,
            ) as resp,
        ):
            if resp.status_code != 200:
                return f"Download failed: {resp.status_code}"
            with open(dest_path, "wb") as f:
                async for chunk in resp.aiter_bytes(chunk_size=5 * 1024 * 1024):
                    f.write(chunk)
        return None

    async def export_file(
        self,
        path: str,
        export_format: str | None = None,
    ) -> tuple[bytes | None, str | None]:
        """Export a non-downloadable file (e.g. .paper) via /2/files/export.

        Uses the recommended new API for Paper-as-files.
        Returns (content_bytes, error_message).
        """
        api_arg: dict[str, str] = {"path": path}
        if export_format:
            api_arg["export_format"] = export_format
        resp = await self._content_request("/2/files/export", api_arg)
        if resp.status_code != 200:
            return None, f"Export failed: {resp.status_code} - {resp.text}"
        return resp.content, None

    async def upload_file(
        self,
        path: str,
        content: bytes,
        mode: str = "add",
        autorename: bool = True,
    ) -> dict[str, Any]:
        """Upload a file to Dropbox (up to 150MB)."""
        api_arg = {"path": path, "mode": mode, "autorename": autorename}
        resp = await self._content_request("/2/files/upload", api_arg, content)
        if resp.status_code != 200:
            raise ValueError(f"Upload failed: {resp.status_code} - {resp.text}")
        return resp.json()

    async def create_paper_doc(
        self, path: str, markdown_content: str
    ) -> dict[str, Any]:
        """Create a Dropbox Paper document from markdown."""
        token = await self._get_valid_token()
        api_arg = {"import_format": "markdown", "path": path}
        headers = {
            "Authorization": f"Bearer {token}",
            "Dropbox-API-Arg": json.dumps(api_arg),
            "Content-Type": "application/octet-stream",
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{API_BASE}/2/files/paper/create",
                headers=headers,
                content=markdown_content.encode("utf-8"),
                timeout=60.0,
            )
        if resp.status_code != 200:
            raise ValueError(
                f"Paper doc creation failed: {resp.status_code} - {resp.text}"
            )
        return resp.json()

    async def delete_file(self, path: str) -> dict[str, Any]:
        """Delete a file or folder."""
        resp = await self._request("/2/files/delete_v2", {"path": path})
        if resp.status_code != 200:
            raise ValueError(f"Delete failed: {resp.status_code} - {resp.text}")
        return resp.json()

    async def get_current_account(self) -> tuple[dict[str, Any] | None, str | None]:
        """Get current user's account info."""
        resp = await self._request("/2/users/get_current_account", None)
        if resp.status_code != 200:
            return None, f"Failed to get account: {resp.status_code}"
        return resp.json(), None
