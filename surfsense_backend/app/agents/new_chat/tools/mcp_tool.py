"""MCP Tool Factory.

This module creates LangChain tools from MCP servers using the Model Context Protocol.
Tools are dynamically discovered from MCP servers - no manual configuration needed.

Supports both transport types:
- stdio: Local process-based MCP servers (command, args, env)
- streamable-http/http/sse: Remote HTTP-based MCP servers (url, headers)

All MCP tools are unconditionally gated by HITL (Human-in-the-Loop) approval.
Per the MCP spec: "Clients MUST consider tool annotations to be untrusted unless
they come from trusted servers."  Users can bypass HITL for specific tools by
clicking "Always Allow", which adds the tool name to the connector's
``config.trusted_tools`` allow-list.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.utils.oauth_security import TokenEncryption

from langchain_core.tools import StructuredTool
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from pydantic import BaseModel, Field, create_model
from sqlalchemy import cast, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.tools.hitl import request_approval
from app.agents.new_chat.tools.mcp_client import MCPClient
from app.db import SearchSourceConnector, SearchSourceConnectorType
from app.services.mcp_oauth.registry import MCP_SERVICES, get_service_by_connector_type

logger = logging.getLogger(__name__)

_MCP_CACHE_TTL_SECONDS = 300  # 5 minutes
_MCP_CACHE_MAX_SIZE = 50
_MCP_DISCOVERY_TIMEOUT_SECONDS = 30
_mcp_tools_cache: dict[int, tuple[float, list[StructuredTool]]] = {}


def _evict_expired_mcp_cache() -> None:
    """Remove expired entries from the MCP tools cache to prevent unbounded growth."""
    now = time.monotonic()
    expired = [
        k
        for k, (ts, _) in _mcp_tools_cache.items()
        if now - ts >= _MCP_CACHE_TTL_SECONDS
    ]
    for k in expired:
        del _mcp_tools_cache[k]
    if expired:
        logger.debug("Evicted %d expired MCP cache entries", len(expired))


def _create_dynamic_input_model_from_schema(
    tool_name: str,
    input_schema: dict[str, Any],
) -> type[BaseModel]:
    """Create a Pydantic model from MCP tool's JSON schema."""
    properties = input_schema.get("properties", {})
    required_fields = input_schema.get("required", [])

    field_definitions = {}
    for param_name, param_schema in properties.items():
        param_description = param_schema.get("description", "")
        is_required = param_name in required_fields

        if is_required:
            field_definitions[param_name] = (
                Any,
                Field(..., description=param_description),
            )
        else:
            field_definitions[param_name] = (
                Any | None,
                Field(None, description=param_description),
            )

    model_name = f"{tool_name.replace(' ', '').replace('-', '_')}Input"
    return create_model(model_name, **field_definitions)


async def _create_mcp_tool_from_definition_stdio(
    tool_def: dict[str, Any],
    mcp_client: MCPClient,
    *,
    connector_name: str = "",
    connector_id: int | None = None,
    trusted_tools: list[str] | None = None,
) -> StructuredTool:
    """Create a LangChain tool from an MCP tool definition (stdio transport).

    All MCP tools are unconditionally wrapped with HITL approval.
    ``request_approval()`` is called OUTSIDE the try/except so that
    ``GraphInterrupt`` propagates cleanly to LangGraph.
    """
    tool_name = tool_def.get("name", "unnamed_tool")
    tool_description = tool_def.get("description", "No description provided")
    input_schema = tool_def.get("input_schema", {"type": "object", "properties": {}})

    logger.debug("MCP tool '%s' input schema: %s", tool_name, input_schema)

    input_model = _create_dynamic_input_model_from_schema(tool_name, input_schema)

    async def mcp_tool_call(**kwargs) -> str:
        """Execute the MCP tool call via the client with retry support."""
        logger.debug("MCP tool '%s' called", tool_name)

        # HITL — OUTSIDE try/except so GraphInterrupt propagates to LangGraph
        hitl_result = request_approval(
            action_type="mcp_tool_call",
            tool_name=tool_name,
            params=kwargs,
            context={
                "mcp_server": connector_name,
                "tool_description": tool_description,
                "mcp_transport": "stdio",
                "mcp_connector_id": connector_id,
            },
            trusted_tools=trusted_tools,
        )
        if hitl_result.rejected:
            return "Tool call rejected by user."
        call_kwargs = {k: v for k, v in hitl_result.params.items() if v is not None}

        try:
            async with mcp_client.connect():
                result = await mcp_client.call_tool(tool_name, call_kwargs)
                return str(result)
        except RuntimeError as e:
            logger.error("MCP tool '%s' connection failed after retries: %s", tool_name, e)
            return f"Error: MCP tool '{tool_name}' connection failed after retries: {e!s}"
        except Exception as e:
            logger.exception("MCP tool '%s' execution failed: %s", tool_name, e)
            return f"Error: MCP tool '{tool_name}' execution failed: {e!s}"

    tool = StructuredTool(
        name=tool_name,
        description=tool_description,
        coroutine=mcp_tool_call,
        args_schema=input_model,
        metadata={
            "mcp_input_schema": input_schema,
            "mcp_transport": "stdio",
            "hitl": True,
            "hitl_dedup_key": next(iter(input_schema.get("required", [])), None),
        },
    )

    logger.debug("Created MCP tool (stdio): '%s'", tool_name)
    return tool


async def _create_mcp_tool_from_definition_http(
    tool_def: dict[str, Any],
    url: str,
    headers: dict[str, str],
    *,
    connector_name: str = "",
    connector_id: int | None = None,
    trusted_tools: list[str] | None = None,
    readonly_tools: frozenset[str] | None = None,
    tool_name_prefix: str | None = None,
) -> StructuredTool:
    """Create a LangChain tool from an MCP tool definition (HTTP transport).

    Write tools are wrapped with HITL approval; read-only tools (listed in
    ``readonly_tools``) execute immediately without user confirmation.

    When ``tool_name_prefix`` is set (multi-account disambiguation), the
    tool exposed to the LLM gets a prefixed name (e.g. ``linear_25_list_issues``)
    but the actual MCP ``call_tool`` still uses the original name.
    """
    original_tool_name = tool_def.get("name", "unnamed_tool")
    tool_description = tool_def.get("description", "No description provided")
    input_schema = tool_def.get("input_schema", {"type": "object", "properties": {}})
    is_readonly = readonly_tools is not None and original_tool_name in readonly_tools

    exposed_name = (
        f"{tool_name_prefix}_{original_tool_name}"
        if tool_name_prefix
        else original_tool_name
    )
    if tool_name_prefix:
        tool_description = f"[Account: {connector_name}] {tool_description}"

    logger.debug("MCP HTTP tool '%s' input schema: %s", exposed_name, input_schema)

    input_model = _create_dynamic_input_model_from_schema(exposed_name, input_schema)

    async def _do_mcp_call(
        call_headers: dict[str, str],
        call_kwargs: dict[str, Any],
    ) -> str:
        """Execute a single MCP HTTP call with the given headers."""
        async with (
            streamablehttp_client(url, headers=call_headers) as (read, write, _),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            response = await session.call_tool(
                original_tool_name, arguments=call_kwargs,
            )

            result = []
            for content in response.content:
                if hasattr(content, "text"):
                    result.append(content.text)
                elif hasattr(content, "data"):
                    result.append(str(content.data))
                else:
                    result.append(str(content))

            return "\n".join(result) if result else ""

    async def mcp_http_tool_call(**kwargs) -> str:
        """Execute the MCP tool call via HTTP transport."""
        logger.debug("MCP HTTP tool '%s' called", exposed_name)

        if is_readonly:
            call_kwargs = {k: v for k, v in kwargs.items() if v is not None}
        else:
            hitl_result = request_approval(
                action_type="mcp_tool_call",
                tool_name=exposed_name,
                params=kwargs,
                context={
                    "mcp_server": connector_name,
                    "tool_description": tool_description,
                    "mcp_transport": "http",
                    "mcp_connector_id": connector_id,
                },
                trusted_tools=trusted_tools,
            )
            if hitl_result.rejected:
                return "Tool call rejected by user."
            call_kwargs = {k: v for k, v in hitl_result.params.items() if v is not None}

        try:
            result_str = await _do_mcp_call(headers, call_kwargs)
            logger.debug("MCP HTTP tool '%s' succeeded (len=%d)", exposed_name, len(result_str))
            return result_str

        except Exception as first_err:
            if not _is_auth_error(first_err) or connector_id is None:
                logger.exception("MCP HTTP tool '%s' execution failed: %s", exposed_name, first_err)
                return f"Error: MCP HTTP tool '{exposed_name}' execution failed: {first_err!s}"

            logger.warning(
                "MCP HTTP tool '%s' got 401 — attempting token refresh for connector %s",
                exposed_name, connector_id,
            )
            fresh_headers = await _force_refresh_and_get_headers(connector_id)
            if fresh_headers is None:
                await _mark_connector_auth_expired(connector_id)
                return (
                    f"Error: MCP tool '{exposed_name}' authentication expired. "
                    "Please re-authenticate the connector in your settings."
                )

            try:
                result_str = await _do_mcp_call(fresh_headers, call_kwargs)
                logger.info(
                    "MCP HTTP tool '%s' succeeded after 401 recovery",
                    exposed_name,
                )
                return result_str
            except Exception as retry_err:
                logger.exception(
                    "MCP HTTP tool '%s' still failing after token refresh: %s",
                    exposed_name, retry_err,
                )
                if _is_auth_error(retry_err):
                    await _mark_connector_auth_expired(connector_id)
                    return (
                        f"Error: MCP tool '{exposed_name}' authentication expired. "
                        "Please re-authenticate the connector in your settings."
                    )
                return f"Error: MCP HTTP tool '{exposed_name}' execution failed: {retry_err!s}"

    tool = StructuredTool(
        name=exposed_name,
        description=tool_description,
        coroutine=mcp_http_tool_call,
        args_schema=input_model,
        metadata={
            "mcp_input_schema": input_schema,
            "mcp_transport": "http",
            "mcp_url": url,
            "hitl": not is_readonly,
            "hitl_dedup_key": next(iter(input_schema.get("required", [])), None),
            "mcp_original_tool_name": original_tool_name,
            "mcp_connector_id": connector_id,
        },
    )

    logger.debug("Created MCP tool (HTTP): '%s'", exposed_name)
    return tool


async def _load_stdio_mcp_tools(
    connector_id: int,
    connector_name: str,
    server_config: dict[str, Any],
    trusted_tools: list[str] | None = None,
) -> list[StructuredTool]:
    """Load tools from a stdio-based MCP server."""
    tools: list[StructuredTool] = []

    command = server_config.get("command")
    if not command or not isinstance(command, str):
        logger.warning(
            "MCP connector %d (name: '%s') missing or invalid command field, skipping",
            connector_id, connector_name,
        )
        return tools

    args = server_config.get("args", [])
    if not isinstance(args, list):
        logger.warning(
            "MCP connector %d (name: '%s') has invalid args field (must be list), skipping",
            connector_id, connector_name,
        )
        return tools

    env = server_config.get("env", {})
    if not isinstance(env, dict):
        logger.warning(
            "MCP connector %d (name: '%s') has invalid env field (must be dict), skipping",
            connector_id, connector_name,
        )
        return tools

    mcp_client = MCPClient(command, args, env)

    async with mcp_client.connect():
        tool_definitions = await mcp_client.list_tools()

        logger.info(
            "Discovered %d tools from stdio MCP server '%s' (connector %d)",
            len(tool_definitions), command, connector_id,
        )

    for tool_def in tool_definitions:
        try:
            tool = await _create_mcp_tool_from_definition_stdio(
                tool_def,
                mcp_client,
                connector_name=connector_name,
                connector_id=connector_id,
                trusted_tools=trusted_tools,
            )
            tools.append(tool)
        except Exception as e:
            logger.exception(
                "Failed to create tool '%s' from connector %d: %s",
                tool_def.get("name"), connector_id, e,
            )

    return tools


async def _load_http_mcp_tools(
    connector_id: int,
    connector_name: str,
    server_config: dict[str, Any],
    trusted_tools: list[str] | None = None,
    allowed_tools: list[str] | None = None,
    readonly_tools: frozenset[str] | None = None,
    tool_name_prefix: str | None = None,
) -> list[StructuredTool]:
    """Load tools from an HTTP-based MCP server.

    Args:
        allowed_tools: If non-empty, only tools whose names appear in this
            list are loaded.  Empty/None means load everything (used for
            user-managed generic MCP servers).
        readonly_tools: Tool names that skip HITL approval (read-only operations).
        tool_name_prefix: If set, each tool name is prefixed for multi-account
            disambiguation (e.g. ``linear_25``).
    """
    tools: list[StructuredTool] = []

    url = server_config.get("url")
    if not url or not isinstance(url, str):
        logger.warning(
            "MCP connector %d (name: '%s') missing or invalid url field, skipping",
            connector_id, connector_name,
        )
        return tools

    headers = server_config.get("headers", {})
    if not isinstance(headers, dict):
        logger.warning(
            "MCP connector %d (name: '%s') has invalid headers field (must be dict), skipping",
            connector_id, connector_name,
        )
        return tools

    allowed_set = set(allowed_tools) if allowed_tools else None

    async def _discover(disc_headers: dict[str, str]) -> list[dict[str, Any]]:
        """Connect, initialize, and list tools from the MCP server."""
        async with (
            streamablehttp_client(url, headers=disc_headers) as (read, write, _),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            response = await session.list_tools()
            return [
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "input_schema": tool.inputSchema
                    if hasattr(tool, "inputSchema")
                    else {},
                }
                for tool in response.tools
            ]

    try:
        tool_definitions = await _discover(headers)
    except Exception as first_err:
        if not _is_auth_error(first_err) or connector_id is None:
            logger.exception(
                "Failed to connect to HTTP MCP server at '%s' (connector %d): %s",
                url, connector_id, first_err,
            )
            return tools

        logger.warning(
            "HTTP MCP discovery for connector %d got 401 — attempting token refresh",
            connector_id,
        )
        fresh_headers = await _force_refresh_and_get_headers(connector_id)
        if fresh_headers is None:
            await _mark_connector_auth_expired(connector_id)
            logger.error(
                "HTTP MCP discovery for connector %d: token refresh failed, marking auth_expired",
                connector_id,
            )
            return tools

        try:
            tool_definitions = await _discover(fresh_headers)
            headers = fresh_headers
            logger.info(
                "HTTP MCP discovery for connector %d succeeded after 401 recovery",
                connector_id,
            )
        except Exception as retry_err:
            logger.exception(
                "HTTP MCP discovery for connector %d still failing after refresh: %s",
                connector_id, retry_err,
            )
            if _is_auth_error(retry_err):
                await _mark_connector_auth_expired(connector_id)
            return tools

    total_discovered = len(tool_definitions)

    if allowed_set:
        tool_definitions = [
            td for td in tool_definitions if td["name"] in allowed_set
        ]
        logger.info(
            "HTTP MCP server '%s' (connector %d): %d/%d tools after allowlist filter",
            url, connector_id, len(tool_definitions), total_discovered,
        )
    else:
        logger.info(
            "Discovered %d tools from HTTP MCP server '%s' (connector %d) — no allowlist, loading all",
            total_discovered, url, connector_id,
        )

    for tool_def in tool_definitions:
        try:
            tool = await _create_mcp_tool_from_definition_http(
                tool_def,
                url,
                headers,
                connector_name=connector_name,
                connector_id=connector_id,
                trusted_tools=trusted_tools,
                readonly_tools=readonly_tools,
                tool_name_prefix=tool_name_prefix,
            )
            tools.append(tool)
        except Exception as e:
            logger.exception(
                "Failed to create HTTP tool '%s' from connector %d: %s",
                tool_def.get("name"), connector_id, e,
            )

    return tools


_TOKEN_REFRESH_BUFFER_SECONDS = 300  # refresh 5 min before expiry

_token_enc: TokenEncryption | None = None


def _get_token_enc() -> TokenEncryption:
    global _token_enc
    if _token_enc is None:
        from app.config import config as app_config
        from app.utils.oauth_security import TokenEncryption

        _token_enc = TokenEncryption(app_config.SECRET_KEY)
    return _token_enc


def _inject_oauth_headers(
    cfg: dict[str, Any],
    server_config: dict[str, Any],
) -> dict[str, Any] | None:
    """Decrypt the MCP OAuth access token and inject it into server_config headers.

    The DB never stores plaintext tokens in ``server_config.headers``.  This
    function decrypts ``mcp_oauth.access_token`` at runtime and returns a
    *copy* of ``server_config`` with the Authorization header set.
    """
    mcp_oauth = cfg.get("mcp_oauth", {})
    encrypted_token = mcp_oauth.get("access_token")
    if not encrypted_token:
        return server_config

    try:
        access_token = _get_token_enc().decrypt_token(encrypted_token)

        result = dict(server_config)
        result["headers"] = {
            **server_config.get("headers", {}),
            "Authorization": f"Bearer {access_token}",
        }
        return result
    except Exception:
        logger.error(
            "Failed to decrypt MCP OAuth token — connector will be skipped",
            exc_info=True,
        )
        return None


async def _refresh_connector_token(
    session: AsyncSession,
    connector: "SearchSourceConnector",
) -> str | None:
    """Refresh the OAuth token for an MCP connector and persist the result.

    This is the shared core used by both proactive (pre-expiry) and reactive
    (401 recovery) refresh paths.  It handles:
    - Decrypting the current refresh token / client secret
    - Calling the token endpoint
    - Encrypting and persisting the new tokens
    - Clearing ``auth_expired`` if it was set
    - Invalidating the MCP tools cache

    Returns the **plaintext** new access token on success, or ``None`` on
    failure (no refresh token, IdP error, etc.).
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy.orm.attributes import flag_modified

    from app.services.mcp_oauth.discovery import refresh_access_token

    cfg = connector.config or {}
    mcp_oauth = cfg.get("mcp_oauth", {})

    refresh_token = mcp_oauth.get("refresh_token")
    if not refresh_token:
        logger.warning(
            "MCP connector %s: no refresh_token available",
            connector.id,
        )
        return None

    enc = _get_token_enc()
    decrypted_refresh = enc.decrypt_token(refresh_token)
    decrypted_secret = (
        enc.decrypt_token(mcp_oauth["client_secret"])
        if mcp_oauth.get("client_secret")
        else ""
    )

    token_json = await refresh_access_token(
        token_endpoint=mcp_oauth["token_endpoint"],
        refresh_token=decrypted_refresh,
        client_id=mcp_oauth["client_id"],
        client_secret=decrypted_secret,
    )

    new_access = token_json.get("access_token")
    if not new_access:
        logger.warning(
            "MCP connector %s: token refresh returned no access_token",
            connector.id,
        )
        return None

    new_expires_at = None
    if token_json.get("expires_in"):
        new_expires_at = datetime.now(UTC) + timedelta(
            seconds=int(token_json["expires_in"])
        )

    updated_oauth = dict(mcp_oauth)
    updated_oauth["access_token"] = enc.encrypt_token(new_access)
    if token_json.get("refresh_token"):
        updated_oauth["refresh_token"] = enc.encrypt_token(
            token_json["refresh_token"]
        )
    updated_oauth["expires_at"] = (
        new_expires_at.isoformat() if new_expires_at else None
    )

    updated_cfg = {**cfg, "mcp_oauth": updated_oauth}
    updated_cfg.pop("auth_expired", None)
    connector.config = updated_cfg
    flag_modified(connector, "config")
    await session.commit()
    await session.refresh(connector)

    invalidate_mcp_tools_cache(connector.search_space_id)

    return new_access


async def _maybe_refresh_mcp_oauth_token(
    session: AsyncSession,
    connector: "SearchSourceConnector",
    cfg: dict[str, Any],
    server_config: dict[str, Any],
) -> dict[str, Any]:
    """Refresh the access token for an MCP OAuth connector if it is about to expire.

    Returns the (possibly updated) ``server_config``.
    """
    from datetime import UTC, datetime, timedelta

    mcp_oauth = cfg.get("mcp_oauth", {})
    expires_at_str = mcp_oauth.get("expires_at")
    if not expires_at_str:
        return server_config

    try:
        expires_at = datetime.fromisoformat(expires_at_str)
        if expires_at.tzinfo is None:
            from datetime import timezone
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if datetime.now(UTC) < expires_at - timedelta(seconds=_TOKEN_REFRESH_BUFFER_SECONDS):
            return server_config
    except (ValueError, TypeError):
        return server_config

    try:
        new_access = await _refresh_connector_token(session, connector)
        if not new_access:
            return server_config

        logger.info("Proactively refreshed MCP OAuth token for connector %s", connector.id)

        refreshed_config = dict(server_config)
        refreshed_config["headers"] = {
            **server_config.get("headers", {}),
            "Authorization": f"Bearer {new_access}",
        }
        return refreshed_config

    except Exception:
        logger.warning(
            "Failed to refresh MCP OAuth token for connector %s",
            connector.id,
            exc_info=True,
        )
        return server_config


# ---------------------------------------------------------------------------
# Reactive 401 handling helpers
# ---------------------------------------------------------------------------


def _is_auth_error(exc: Exception) -> bool:
    """Check if an exception indicates an HTTP 401 authentication failure."""
    try:
        import httpx

        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code == 401
    except ImportError:
        pass
    err_str = str(exc).lower()
    return "401" in err_str or "unauthorized" in err_str


async def _force_refresh_and_get_headers(
    connector_id: int,
) -> dict[str, str] | None:
    """Force-refresh OAuth token for a connector and return fresh HTTP headers.

    Opens a **new** DB session so this can be called from inside tool closures
    that don't have access to the original session.

    Returns ``None`` when the connector is not OAuth-backed, has no
    refresh token, or the refresh itself fails.
    """
    from app.db import async_session_maker

    try:
        async with async_session_maker() as session:
            result = await session.execute(
                select(SearchSourceConnector).filter(
                    SearchSourceConnector.id == connector_id,
                )
            )
            connector = result.scalars().first()
            if not connector:
                return None

            cfg = connector.config or {}
            if not cfg.get("mcp_oauth"):
                return None

            server_config = cfg.get("server_config", {})

            new_access = await _refresh_connector_token(session, connector)
            if not new_access:
                return None

            logger.info(
                "Force-refreshed MCP OAuth token for connector %s (401 recovery)",
                connector_id,
            )
            return {
                **server_config.get("headers", {}),
                "Authorization": f"Bearer {new_access}",
            }

    except Exception:
        logger.warning(
            "Failed to force-refresh MCP OAuth token for connector %s",
            connector_id,
            exc_info=True,
        )
        return None


async def _mark_connector_auth_expired(connector_id: int) -> None:
    """Set ``config.auth_expired = True`` so the frontend shows re-auth UI."""
    from app.db import async_session_maker

    try:
        async with async_session_maker() as session:
            result = await session.execute(
                select(SearchSourceConnector).filter(
                    SearchSourceConnector.id == connector_id,
                )
            )
            connector = result.scalars().first()
            if not connector:
                return

            cfg = dict(connector.config or {})
            if cfg.get("auth_expired"):
                return

            cfg["auth_expired"] = True
            connector.config = cfg

            from sqlalchemy.orm.attributes import flag_modified

            flag_modified(connector, "config")
            await session.commit()

            logger.info(
                "Marked MCP connector %s as auth_expired after unrecoverable 401",
                connector_id,
            )
            invalidate_mcp_tools_cache(connector.search_space_id)

    except Exception:
        logger.warning(
            "Failed to mark connector %s as auth_expired",
            connector_id,
            exc_info=True,
        )


def invalidate_mcp_tools_cache(search_space_id: int | None = None) -> None:
    """Invalidate cached MCP tools.

    Args:
        search_space_id: If provided, only invalidate for this search space.
                        If None, invalidate all cached MCP tools.
    """
    if search_space_id is not None:
        _mcp_tools_cache.pop(search_space_id, None)
    else:
        _mcp_tools_cache.clear()


async def load_mcp_tools(
    session: AsyncSession,
    search_space_id: int,
) -> list[StructuredTool]:
    """Load all MCP tools from user's active MCP server connectors.

    This discovers tools dynamically from MCP servers using the protocol.
    Supports both stdio (local process) and HTTP (remote server) transports.

    Results are cached per search space for up to 5 minutes to avoid
    re-spawning MCP server processes on every chat message.
    """
    _evict_expired_mcp_cache()

    now = time.monotonic()
    cached = _mcp_tools_cache.get(search_space_id)
    if cached is not None:
        cached_at, cached_tools = cached
        if now - cached_at < _MCP_CACHE_TTL_SECONDS:
            logger.info(
                "Using cached MCP tools for search space %s (%d tools, age=%.0fs)",
                search_space_id,
                len(cached_tools),
                now - cached_at,
            )
            return list(cached_tools)

    try:
        # Find all connectors with MCP server config: generic MCP_CONNECTOR type
        # and service-specific types (LINEAR_CONNECTOR, etc.) created via MCP OAuth.
        # Cast JSON -> JSONB so we can use has_key to filter by the presence of "server_config".
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.search_space_id == search_space_id,
                cast(SearchSourceConnector.config, JSONB).has_key("server_config"),  # noqa: W601
            ),
        )

        connectors = list(result.scalars())

        # Group connectors by type to detect multi-account scenarios.
        # When >1 connector shares the same type, tool names would collide
        # so we prefix them with "{service_key}_{connector_id}_".
        type_groups: dict[str, list[SearchSourceConnector]] = defaultdict(list)
        for connector in connectors:
            ct = (
                connector.connector_type.value
                if hasattr(connector.connector_type, "value")
                else str(connector.connector_type)
            )
            type_groups[ct].append(connector)

        multi_account_types: set[str] = {
            ct for ct, group in type_groups.items() if len(group) > 1
        }
        if multi_account_types:
            logger.info(
                "Multi-account detected for connector types: %s",
                multi_account_types,
            )

        discovery_tasks: list[dict[str, Any]] = []
        for connector in connectors:
            try:
                cfg = connector.config or {}
                server_config = cfg.get("server_config", {})

                if not server_config or not isinstance(server_config, dict):
                    logger.warning(
                        "MCP connector %d (name: '%s') has invalid or missing server_config, skipping",
                        connector.id, connector.name,
                    )
                    continue

                if cfg.get("mcp_oauth"):
                    server_config = await _maybe_refresh_mcp_oauth_token(
                        session, connector, cfg, server_config,
                    )
                    cfg = connector.config or {}
                    server_config = _inject_oauth_headers(cfg, server_config)
                    if server_config is None:
                        logger.warning(
                            "Skipping MCP connector %d — OAuth token decryption failed",
                            connector.id,
                        )
                        await _mark_connector_auth_expired(connector.id)
                        continue

                trusted_tools = cfg.get("trusted_tools", [])

                ct = (
                    connector.connector_type.value
                    if hasattr(connector.connector_type, "value")
                    else str(connector.connector_type)
                )

                svc_cfg = get_service_by_connector_type(ct)
                allowed_tools = svc_cfg.allowed_tools if svc_cfg else []
                readonly_tools = svc_cfg.readonly_tools if svc_cfg else frozenset()

                tool_name_prefix: str | None = None
                if ct in multi_account_types and svc_cfg:
                    service_key = next(
                        (k for k, v in MCP_SERVICES.items() if v is svc_cfg),
                        None,
                    )
                    if service_key:
                        tool_name_prefix = f"{service_key}_{connector.id}"

                discovery_tasks.append({
                    "connector_id": connector.id,
                    "connector_name": connector.name,
                    "server_config": server_config,
                    "trusted_tools": trusted_tools,
                    "allowed_tools": allowed_tools,
                    "readonly_tools": readonly_tools,
                    "tool_name_prefix": tool_name_prefix,
                    "transport": server_config.get("transport", "stdio"),
                })

            except Exception as e:
                logger.exception(
                    "Failed to prepare MCP connector %d: %s",
                    connector.id, e,
                )

        async def _discover_one(task: dict[str, Any]) -> list[StructuredTool]:
            try:
                if task["transport"] in ("streamable-http", "http", "sse"):
                    return await asyncio.wait_for(
                        _load_http_mcp_tools(
                            task["connector_id"],
                            task["connector_name"],
                            task["server_config"],
                            trusted_tools=task["trusted_tools"],
                            allowed_tools=task["allowed_tools"],
                            readonly_tools=task["readonly_tools"],
                            tool_name_prefix=task["tool_name_prefix"],
                        ),
                        timeout=_MCP_DISCOVERY_TIMEOUT_SECONDS,
                    )
                else:
                    return await asyncio.wait_for(
                        _load_stdio_mcp_tools(
                            task["connector_id"],
                            task["connector_name"],
                            task["server_config"],
                            trusted_tools=task["trusted_tools"],
                        ),
                        timeout=_MCP_DISCOVERY_TIMEOUT_SECONDS,
                    )
            except asyncio.TimeoutError:
                logger.error(
                    "MCP connector %d timed out after %ds during discovery",
                    task["connector_id"], _MCP_DISCOVERY_TIMEOUT_SECONDS,
                )
                return []
            except Exception as e:
                logger.exception(
                    "Failed to load tools from MCP connector %d: %s",
                    task["connector_id"], e,
                )
                return []

        results = await asyncio.gather(*[_discover_one(t) for t in discovery_tasks])
        tools: list[StructuredTool] = [
            tool for sublist in results for tool in sublist
        ]

        _mcp_tools_cache[search_space_id] = (now, tools)

        if len(_mcp_tools_cache) > _MCP_CACHE_MAX_SIZE:
            oldest_key = min(_mcp_tools_cache, key=lambda k: _mcp_tools_cache[k][0])
            del _mcp_tools_cache[oldest_key]

        logger.info("Loaded %d MCP tools for search space %d", len(tools), search_space_id)
        return tools

    except Exception as e:
        logger.exception("Failed to load MCP tools: %s", e)
        return []
