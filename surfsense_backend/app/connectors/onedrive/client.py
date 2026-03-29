"""Microsoft OneDrive API client using Microsoft Graph API v1.0."""

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

GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"


class OneDriveClient:
    """Client for Microsoft OneDrive via the Graph API."""

    def __init__(self, session: AsyncSession, connector_id: int):
        self._session = session
        self._connector_id = connector_id

    async def _get_valid_token(self) -> str:
        """Get a valid access token, refreshing if needed."""
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
        token_encryption = TokenEncryption(config.SECRET_KEY) if config.SECRET_KEY else None

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
            raise ValueError("OneDrive token expired and no refresh token available")

        token_data = await self._refresh_token(refresh_token)

        new_access = token_data["access_token"]
        new_refresh = token_data.get("refresh_token", refresh_token)
        expires_in = token_data.get("expires_in")

        new_expires_at = None
        if expires_in:
            new_expires_at = datetime.now(UTC) + timedelta(seconds=int(expires_in))

        if token_encryption:
            cfg["access_token"] = token_encryption.encrypt_token(new_access)
            cfg["refresh_token"] = token_encryption.encrypt_token(new_refresh)
        else:
            cfg["access_token"] = new_access
            cfg["refresh_token"] = new_refresh

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
            "client_id": config.MICROSOFT_CLIENT_ID,
            "client_secret": config.MICROSOFT_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": "offline_access User.Read Files.Read.All Files.ReadWrite.All",
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
            raise ValueError(f"OneDrive token refresh failed: {error_detail}")
        return resp.json()

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Make an authenticated request to the Graph API."""
        token = await self._get_valid_token()
        headers = {"Authorization": f"Bearer {token}"}
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        async with httpx.AsyncClient() as client:
            resp = await client.request(
                method,
                f"{GRAPH_API_BASE}{path}",
                headers=headers,
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
            raise ValueError("OneDrive authentication expired (401)")

        return resp

    async def list_children(
        self, item_id: str = "root"
    ) -> tuple[list[dict[str, Any]], str | None]:
        all_items: list[dict[str, Any]] = []
        url = f"/me/drive/items/{item_id}/children"
        params: dict[str, Any] = {
            "$top": 200,
            "$select": "id,name,size,file,folder,parentReference,lastModifiedDateTime,createdDateTime,webUrl,remoteItem,package",
        }
        while url:
            resp = await self._request("GET", url, params=params)
            if resp.status_code != 200:
                return [], f"Failed to list children: {resp.status_code} - {resp.text}"
            data = resp.json()
            all_items.extend(data.get("value", []))
            next_link = data.get("@odata.nextLink")
            if next_link:
                url = next_link.replace(GRAPH_API_BASE, "")
                params = {}
            else:
                url = ""
        return all_items, None

    async def get_item_metadata(
        self, item_id: str
    ) -> tuple[dict[str, Any] | None, str | None]:
        resp = await self._request(
            "GET",
            f"/me/drive/items/{item_id}",
            params={
                "$select": "id,name,size,file,folder,parentReference,lastModifiedDateTime,createdDateTime,webUrl"
            },
        )
        if resp.status_code != 200:
            return None, f"Failed to get item: {resp.status_code} - {resp.text}"
        return resp.json(), None

    async def download_file(self, item_id: str) -> tuple[bytes | None, str | None]:
        token = await self._get_valid_token()
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(
                f"{GRAPH_API_BASE}/me/drive/items/{item_id}/content",
                headers={"Authorization": f"Bearer {token}"},
                timeout=120.0,
            )
        if resp.status_code != 200:
            return None, f"Download failed: {resp.status_code}"
        return resp.content, None

    async def download_file_to_disk(self, item_id: str, dest_path: str) -> str | None:
        """Stream file content to disk. Returns error message on failure."""
        token = await self._get_valid_token()
        async with httpx.AsyncClient(follow_redirects=True) as client:
            async with client.stream(
                "GET",
                f"{GRAPH_API_BASE}/me/drive/items/{item_id}/content",
                headers={"Authorization": f"Bearer {token}"},
                timeout=120.0,
            ) as resp:
                if resp.status_code != 200:
                    return f"Download failed: {resp.status_code}"
                with open(dest_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=5 * 1024 * 1024):
                        f.write(chunk)
        return None

    async def create_file(
        self,
        name: str,
        parent_id: str | None = None,
        content: str | bytes | None = None,
        mime_type: str | None = None,
    ) -> dict[str, Any]:
        """Create (upload) a file in OneDrive."""
        folder_path = f"/me/drive/items/{parent_id or 'root'}"
        if isinstance(content, bytes):
            body = content
        else:
            body = (content or "").encode("utf-8")
        resp = await self._request(
            "PUT",
            f"{folder_path}:/{name}:/content",
            content=body,
            headers={"Content-Type": mime_type or "application/octet-stream"},
        )
        if resp.status_code not in (200, 201):
            raise ValueError(f"File creation failed: {resp.status_code} - {resp.text}")
        return resp.json()

    async def trash_file(self, item_id: str) -> bool:
        """Delete (move to recycle bin) a OneDrive item."""
        resp = await self._request("DELETE", f"/me/drive/items/{item_id}")
        if resp.status_code not in (200, 204):
            raise ValueError(f"Trash failed: {resp.status_code} - {resp.text}")
        return True

    async def get_delta(
        self, folder_id: str | None = None, delta_link: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None, str | None]:
        """Get delta changes. Returns (changes, new_delta_link, error)."""
        all_changes: list[dict[str, Any]] = []
        if delta_link:
            url = delta_link.replace(GRAPH_API_BASE, "")
        elif folder_id:
            url = f"/me/drive/items/{folder_id}/delta"
        else:
            url = "/me/drive/root/delta"

        params: dict[str, Any] = {"$top": 200}
        while url:
            resp = await self._request("GET", url, params=params)
            if resp.status_code != 200:
                return [], None, f"Delta failed: {resp.status_code} - {resp.text}"
            data = resp.json()
            all_changes.extend(data.get("value", []))
            next_link = data.get("@odata.nextLink")
            new_delta_link = data.get("@odata.deltaLink")
            if next_link:
                url = next_link.replace(GRAPH_API_BASE, "")
                params = {}
            else:
                url = ""
        return all_changes, new_delta_link, None
