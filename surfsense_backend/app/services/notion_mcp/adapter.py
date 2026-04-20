"""Notion MCP Adapter.

Connects to Notion's hosted MCP server at ``https://mcp.notion.com/mcp``
and exposes the same method signatures as ``NotionHistoryConnector``'s
write operations so that tool factories can swap with a one-line change.

Includes an optional fallback to ``NotionHistoryConnector`` when the MCP
server returns known serialization errors (GitHub issues #215, #216).
"""

import logging
from datetime import UTC, datetime
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import SearchSourceConnector
from app.schemas.notion_auth_credentials import NotionAuthCredentialsBase
from app.utils.oauth_security import TokenEncryption

from .response_parser import (
    extract_text_from_mcp_response,
    is_mcp_serialization_error,
    parse_create_page_response,
    parse_delete_page_response,
    parse_fetch_page_response,
    parse_health_check_response,
    parse_update_page_response,
)

logger = logging.getLogger(__name__)

NOTION_MCP_URL = "https://mcp.notion.com/mcp"


class NotionMCPAdapter:
    """Routes Notion operations through the hosted MCP server.

    Drop-in replacement for ``NotionHistoryConnector`` write methods.
    Returns the same dict structure so KB sync works unchanged.
    """

    def __init__(self, session: AsyncSession, connector_id: int):
        self._session = session
        self._connector_id = connector_id
        self._access_token: str | None = None

    async def _get_valid_token(self) -> str:
        """Get a valid MCP access token, refreshing if expired."""
        result = await self._session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == self._connector_id
            )
        )
        connector = result.scalars().first()
        if not connector:
            raise ValueError(f"Connector {self._connector_id} not found")

        cfg = connector.config or {}

        if not cfg.get("mcp_mode"):
            raise ValueError(
                f"Connector {self._connector_id} is not an MCP connector"
            )

        access_token = cfg.get("access_token")
        if not access_token:
            raise ValueError("No access token in MCP connector config")

        is_encrypted = cfg.get("_token_encrypted", False)
        if is_encrypted and config.SECRET_KEY:
            token_encryption = TokenEncryption(config.SECRET_KEY)
            access_token = token_encryption.decrypt_token(access_token)

        expires_at_str = cfg.get("expires_at")
        if expires_at_str:
            expires_at = datetime.fromisoformat(expires_at_str)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if expires_at <= datetime.now(UTC):
                from app.routes.notion_mcp_connector_route import refresh_notion_mcp_token

                connector = await refresh_notion_mcp_token(self._session, connector)
                cfg = connector.config or {}
                access_token = cfg.get("access_token", "")
                if is_encrypted and config.SECRET_KEY:
                    token_encryption = TokenEncryption(config.SECRET_KEY)
                    access_token = token_encryption.decrypt_token(access_token)

        self._access_token = access_token
        return access_token

    async def _call_mcp_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> str:
        """Connect to Notion MCP server and call a tool. Returns raw text."""
        token = await self._get_valid_token()
        headers = {"Authorization": f"Bearer {token}"}

        async with (
            streamablehttp_client(NOTION_MCP_URL, headers=headers) as (read, write, _),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            response = await session.call_tool(tool_name, arguments=arguments)
            return extract_text_from_mcp_response(response)

    async def _call_with_fallback(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        parser,
        fallback_method: str | None = None,
        fallback_kwargs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call MCP tool, parse response, and fall back on serialization errors."""
        try:
            raw_text = await self._call_mcp_tool(tool_name, arguments)
            result = parser(raw_text)

            if result.get("mcp_serialization_error") and fallback_method:
                logger.warning(
                    "MCP tool '%s' hit serialization bug, falling back to direct API",
                    tool_name,
                )
                return await self._fallback(fallback_method, fallback_kwargs or {})

            return result

        except Exception as e:
            error_str = str(e)
            if is_mcp_serialization_error(error_str) and fallback_method:
                logger.warning(
                    "MCP tool '%s' raised serialization error, falling back: %s",
                    tool_name,
                    error_str,
                )
                return await self._fallback(fallback_method, fallback_kwargs or {})

            logger.error("MCP tool '%s' failed: %s", tool_name, e, exc_info=True)
            return {"status": "error", "message": f"MCP call failed: {e!s}"}

    async def _fallback(
        self, method_name: str, kwargs: dict[str, Any]
    ) -> dict[str, Any]:
        """Fall back to NotionHistoryConnector for the given method.

        Uses the already-refreshed MCP access token directly with the
        Notion SDK, bypassing the connector's config-based token loading.
        """
        from app.connectors.notion_history import NotionHistoryConnector
        from app.schemas.notion_auth_credentials import NotionAuthCredentialsBase

        token = self._access_token
        if not token:
            token = await self._get_valid_token()

        connector = NotionHistoryConnector(
            session=self._session,
            connector_id=self._connector_id,
        )
        connector._credentials = NotionAuthCredentialsBase(access_token=token)
        connector._using_legacy_token = True

        method = getattr(connector, method_name)
        return await method(**kwargs)

    # ------------------------------------------------------------------
    # Public API — same signatures as NotionHistoryConnector
    # ------------------------------------------------------------------

    async def create_page(
        self,
        title: str,
        content: str,
        parent_page_id: str | None = None,
    ) -> dict[str, Any]:
        arguments: dict[str, Any] = {
            "pages": [
                {
                    "title": title,
                    "content": content,
                }
            ]
        }
        if parent_page_id:
            arguments["pages"][0]["parent_page_url"] = parent_page_id

        return await self._call_with_fallback(
            tool_name="notion-create-pages",
            arguments=arguments,
            parser=parse_create_page_response,
            fallback_method="create_page",
            fallback_kwargs={
                "title": title,
                "content": content,
                "parent_page_id": parent_page_id,
            },
        )

    async def update_page(
        self,
        page_id: str,
        content: str | None = None,
    ) -> dict[str, Any]:
        arguments: dict[str, Any] = {
            "page_id": page_id,
            "command": "replace_content",
        }
        if content:
            arguments["new_str"] = content

        return await self._call_with_fallback(
            tool_name="notion-update-page",
            arguments=arguments,
            parser=parse_update_page_response,
            fallback_method="update_page",
            fallback_kwargs={"page_id": page_id, "content": content},
        )

    async def delete_page(self, page_id: str) -> dict[str, Any]:
        arguments: dict[str, Any] = {
            "page_id": page_id,
            "command": "update_properties",
            "archived": True,
        }

        return await self._call_with_fallback(
            tool_name="notion-update-page",
            arguments=arguments,
            parser=parse_delete_page_response,
            fallback_method="delete_page",
            fallback_kwargs={"page_id": page_id},
        )

    async def fetch_page(self, page_url_or_id: str) -> dict[str, Any]:
        """Fetch page content via ``notion-fetch``."""
        raw_text = await self._call_mcp_tool(
            "notion-fetch", {"url": page_url_or_id}
        )
        return parse_fetch_page_response(raw_text)

    async def health_check(self) -> dict[str, Any]:
        """Check MCP connection via ``notion-get-self``."""
        try:
            raw_text = await self._call_mcp_tool("notion-get-self", {})
            return parse_health_check_response(raw_text)
        except Exception as e:
            return {"status": "error", "message": str(e)}
