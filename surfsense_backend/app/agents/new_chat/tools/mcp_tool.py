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

import logging
import time
from typing import Any

from langchain_core.tools import StructuredTool
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from pydantic import BaseModel, create_model
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.tools.hitl import request_approval
from app.agents.new_chat.tools.mcp_client import MCPClient
from app.db import SearchSourceConnector, SearchSourceConnectorType

logger = logging.getLogger(__name__)

_MCP_CACHE_TTL_SECONDS = 300  # 5 minutes
_MCP_CACHE_MAX_SIZE = 50
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

        from typing import Any as AnyType

        from pydantic import Field

        if is_required:
            field_definitions[param_name] = (
                AnyType,
                Field(..., description=param_description),
            )
        else:
            field_definitions[param_name] = (
                AnyType | None,
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

    logger.info(f"MCP tool '{tool_name}' input schema: {input_schema}")

    input_model = _create_dynamic_input_model_from_schema(tool_name, input_schema)

    async def mcp_tool_call(**kwargs) -> str:
        """Execute the MCP tool call via the client with retry support."""
        logger.info(f"MCP tool '{tool_name}' called with params: {kwargs}")

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
        call_kwargs = hitl_result.params

        try:
            async with mcp_client.connect():
                result = await mcp_client.call_tool(tool_name, call_kwargs)
                return str(result)
        except RuntimeError as e:
            error_msg = f"MCP tool '{tool_name}' connection failed after retries: {e!s}"
            logger.error(error_msg)
            return f"Error: {error_msg}"
        except Exception as e:
            error_msg = f"MCP tool '{tool_name}' execution failed: {e!s}"
            logger.exception(error_msg)
            return f"Error: {error_msg}"

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

    logger.info(f"Created MCP tool (stdio): '{tool_name}'")
    return tool


async def _create_mcp_tool_from_definition_http(
    tool_def: dict[str, Any],
    url: str,
    headers: dict[str, str],
    *,
    connector_name: str = "",
    connector_id: int | None = None,
    trusted_tools: list[str] | None = None,
) -> StructuredTool:
    """Create a LangChain tool from an MCP tool definition (HTTP transport).

    All MCP tools are unconditionally wrapped with HITL approval.
    ``request_approval()`` is called OUTSIDE the try/except so that
    ``GraphInterrupt`` propagates cleanly to LangGraph.
    """
    tool_name = tool_def.get("name", "unnamed_tool")
    tool_description = tool_def.get("description", "No description provided")
    input_schema = tool_def.get("input_schema", {"type": "object", "properties": {}})

    logger.info(f"MCP HTTP tool '{tool_name}' input schema: {input_schema}")

    input_model = _create_dynamic_input_model_from_schema(tool_name, input_schema)

    async def mcp_http_tool_call(**kwargs) -> str:
        """Execute the MCP tool call via HTTP transport."""
        logger.info(f"MCP HTTP tool '{tool_name}' called with params: {kwargs}")

        # HITL — OUTSIDE try/except so GraphInterrupt propagates to LangGraph
        hitl_result = request_approval(
            action_type="mcp_tool_call",
            tool_name=tool_name,
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
        call_kwargs = hitl_result.params

        try:
            async with (
                streamablehttp_client(url, headers=headers) as (read, write, _),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                response = await session.call_tool(tool_name, arguments=call_kwargs)

                result = []
                for content in response.content:
                    if hasattr(content, "text"):
                        result.append(content.text)
                    elif hasattr(content, "data"):
                        result.append(str(content.data))
                    else:
                        result.append(str(content))

                result_str = "\n".join(result) if result else ""
                logger.info(
                    f"MCP HTTP tool '{tool_name}' succeeded: {result_str[:200]}"
                )
                return result_str

        except Exception as e:
            error_msg = f"MCP HTTP tool '{tool_name}' execution failed: {e!s}"
            logger.exception(error_msg)
            return f"Error: {error_msg}"

    tool = StructuredTool(
        name=tool_name,
        description=tool_description,
        coroutine=mcp_http_tool_call,
        args_schema=input_model,
        metadata={
            "mcp_input_schema": input_schema,
            "mcp_transport": "http",
            "mcp_url": url,
            "hitl": True,
            "hitl_dedup_key": next(iter(input_schema.get("required", [])), None),
        },
    )

    logger.info(f"Created MCP tool (HTTP): '{tool_name}'")
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
            f"MCP connector {connector_id} (name: '{connector_name}') missing or invalid command field, skipping"
        )
        return tools

    args = server_config.get("args", [])
    if not isinstance(args, list):
        logger.warning(
            f"MCP connector {connector_id} (name: '{connector_name}') has invalid args field (must be list), skipping"
        )
        return tools

    env = server_config.get("env", {})
    if not isinstance(env, dict):
        logger.warning(
            f"MCP connector {connector_id} (name: '{connector_name}') has invalid env field (must be dict), skipping"
        )
        return tools

    mcp_client = MCPClient(command, args, env)

    async with mcp_client.connect():
        tool_definitions = await mcp_client.list_tools()

        logger.info(
            f"Discovered {len(tool_definitions)} tools from stdio MCP server "
            f"'{command}' (connector {connector_id})"
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
                f"Failed to create tool '{tool_def.get('name')}' "
                f"from connector {connector_id}: {e!s}"
            )

    return tools


async def _load_http_mcp_tools(
    connector_id: int,
    connector_name: str,
    server_config: dict[str, Any],
    trusted_tools: list[str] | None = None,
) -> list[StructuredTool]:
    """Load tools from an HTTP-based MCP server."""
    tools: list[StructuredTool] = []

    url = server_config.get("url")
    if not url or not isinstance(url, str):
        logger.warning(
            f"MCP connector {connector_id} (name: '{connector_name}') missing or invalid url field, skipping"
        )
        return tools

    headers = server_config.get("headers", {})
    if not isinstance(headers, dict):
        logger.warning(
            f"MCP connector {connector_id} (name: '{connector_name}') has invalid headers field (must be dict), skipping"
        )
        return tools

    try:
        async with (
            streamablehttp_client(url, headers=headers) as (read, write, _),
            ClientSession(read, write) as session,
        ):
            await session.initialize()

            response = await session.list_tools()
            tool_definitions = []
            for tool in response.tools:
                tool_definitions.append(
                    {
                        "name": tool.name,
                        "description": tool.description or "",
                        "input_schema": tool.inputSchema
                        if hasattr(tool, "inputSchema")
                        else {},
                    }
                )

            logger.info(
                f"Discovered {len(tool_definitions)} tools from HTTP MCP server "
                f"'{url}' (connector {connector_id})"
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
                )
                tools.append(tool)
            except Exception as e:
                logger.exception(
                    f"Failed to create HTTP tool '{tool_def.get('name')}' "
                    f"from connector {connector_id}: {e!s}"
                )

    except Exception as e:
        logger.exception(
            f"Failed to connect to HTTP MCP server at '{url}' (connector {connector_id}): {e!s}"
        )

    return tools


_TOKEN_REFRESH_BUFFER_SECONDS = 300  # refresh 5 min before expiry


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

    refresh_token = mcp_oauth.get("refresh_token")
    if not refresh_token:
        logger.warning(
            "MCP connector %s token expired but no refresh_token available",
            connector.id,
        )
        return server_config

    try:
        from app.config import config as app_config
        from app.services.mcp_oauth.discovery import refresh_access_token
        from app.utils.oauth_security import TokenEncryption

        enc = TokenEncryption(app_config.SECRET_KEY)
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
                "MCP connector %s token refresh returned no access_token",
                connector.id,
            )
            return server_config

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

        updated_server_config = dict(server_config)
        updated_server_config["headers"] = {
            **server_config.get("headers", {}),
            "Authorization": f"Bearer {new_access}",
        }

        from sqlalchemy.orm.attributes import flag_modified

        connector.config = {
            **cfg,
            "server_config": updated_server_config,
            "mcp_oauth": updated_oauth,
        }
        flag_modified(connector, "config")
        await session.commit()
        await session.refresh(connector)

        logger.info("Refreshed MCP OAuth token for connector %s", connector.id)
        return updated_server_config

    except Exception:
        logger.warning(
            "Failed to refresh MCP OAuth token for connector %s",
            connector.id,
            exc_info=True,
        )
        return server_config


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
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.search_space_id == search_space_id,
                SearchSourceConnector.config.has_key("server_config"),  # noqa: W601
            ),
        )

        tools: list[StructuredTool] = []
        for connector in result.scalars():
            try:
                cfg = connector.config or {}
                server_config = cfg.get("server_config", {})
                trusted_tools = cfg.get("trusted_tools", [])

                if not server_config or not isinstance(server_config, dict):
                    logger.warning(
                        f"MCP connector {connector.id} (name: '{connector.name}') has invalid or missing server_config, skipping"
                    )
                    continue

                # Refresh OAuth token for MCP OAuth connectors before connecting
                if cfg.get("mcp_oauth"):
                    server_config = await _maybe_refresh_mcp_oauth_token(
                        session, connector, cfg, server_config,
                    )

                transport = server_config.get("transport", "stdio")

                if transport in ("streamable-http", "http", "sse"):
                    connector_tools = await _load_http_mcp_tools(
                        connector.id,
                        connector.name,
                        server_config,
                        trusted_tools=trusted_tools,
                    )
                else:
                    connector_tools = await _load_stdio_mcp_tools(
                        connector.id,
                        connector.name,
                        server_config,
                        trusted_tools=trusted_tools,
                    )

                tools.extend(connector_tools)

            except Exception as e:
                logger.exception(
                    f"Failed to load tools from MCP connector {connector.id}: {e!s}"
                )

        _mcp_tools_cache[search_space_id] = (now, tools)

        if len(_mcp_tools_cache) > _MCP_CACHE_MAX_SIZE:
            oldest_key = min(_mcp_tools_cache, key=lambda k: _mcp_tools_cache[k][0])
            del _mcp_tools_cache[oldest_key]

        logger.info(f"Loaded {len(tools)} MCP tools for search space {search_space_id}")
        return tools

    except Exception as e:
        logger.exception(f"Failed to load MCP tools: {e!s}")
        return []
