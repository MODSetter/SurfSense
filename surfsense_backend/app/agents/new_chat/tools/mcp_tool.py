"""MCP Tool Factory.

This module creates LangChain tools from user-defined MCP connector configurations.
MCP allows users to add custom API endpoints as tools for the agent to use.

Note on Implementation:
This is a custom implementation for simplicity and flexibility. Alternative approaches:
1. Official MCP SDK (https://github.com/modelcontextprotocol/python-sdk) - for full MCP
   protocol with server processes, but heavier weight
2. LangChain's OpenAPIToolkit - auto-generate tools from OpenAPI specs, but requires users
   to provide/maintain OpenAPI definitions
3. LangChain's RequestsWrapper - simpler HTTP utilities, but less dynamic tool generation

Current approach keeps dependencies minimal and gives users a simple JSON-based config.
"""

import logging
from typing import Any

import httpx
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SearchSourceConnector, SearchSourceConnectorType

logger = logging.getLogger(__name__)


def _build_auth_headers(auth_config: dict[str, Any]) -> dict[str, str]:
    """Build authentication headers from MCP tool auth configuration.

    Args:
        auth_config: Authentication configuration containing:
            - auth_type: "bearer" | "api_key" | "basic" | "none"
            - token: For bearer auth
            - api_key: For API key auth
            - api_key_header: Header name for API key (default: "X-API-Key")
            - username/password: For basic auth

    Returns:
        Dictionary of HTTP headers for authentication

    """
    headers = {}
    auth_type = auth_config.get("auth_type", "none")

    if auth_type == "bearer":
        token = auth_config.get("token", "")
        if token:
            headers["Authorization"] = f"Bearer {token}"

    elif auth_type == "api_key":
        api_key = auth_config.get("api_key", "")
        api_key_header = auth_config.get("api_key_header", "X-API-Key")
        if api_key:
            headers[api_key_header] = api_key

    elif auth_type == "basic":
        username = auth_config.get("username", "")
        password = auth_config.get("password", "")
        if username and password:
            import base64

            credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
            headers["Authorization"] = f"Basic {credentials}"

    return headers


def _create_dynamic_input_model(
    tool_name: str, parameters_schema: dict[str, Any],
) -> type[BaseModel]:
    """Create a Pydantic model from JSON schema for tool parameters.

    Args:
        tool_name: Name of the tool (used for model class name)
        parameters_schema: JSON schema defining the parameters

    Returns:
        Pydantic model class for tool input validation

    """
    properties = parameters_schema.get("properties", {})
    required_fields = parameters_schema.get("required", [])

    # Build Pydantic field definitions
    field_definitions = {}
    for param_name, param_schema in properties.items():
        param_type = param_schema.get("type", "string")
        param_description = param_schema.get("description", "")
        is_required = param_name in required_fields

        # Map JSON schema types to Python types
        python_type = str  # default
        if param_type == "number":
            python_type = float
        elif param_type == "integer":
            python_type = int
        elif param_type == "boolean":
            python_type = bool
        elif param_type == "array":
            python_type = list
        elif param_type == "object":
            python_type = dict

        # Create field with optional default
        if is_required:
            field_definitions[param_name] = (
                python_type,
                Field(..., description=param_description),
            )
        else:
            field_definitions[param_name] = (
                python_type | None,
                Field(None, description=param_description),
            )

    # Create dynamic model
    model_name = f"{tool_name.replace(' ', '')}Input"
    return create_model(model_name, **field_definitions)


async def _create_mcp_tool_instance(
    tool_config: dict[str, Any], connector_id: int,
) -> StructuredTool:
    """Create a single LangChain tool from an MCP tool configuration.

    Args:
        tool_config: Tool configuration containing:
            - name: Tool name
            - description: Tool description
            - endpoint: API endpoint URL
            - method: HTTP method (GET, POST, etc.)
            - auth_type: Authentication type
            - auth_config: Auth credentials
            - parameters: JSON schema for parameters
            - verify_ssl: Whether to verify SSL certificates (default: True)
        connector_id: ID of the parent MCP connector

    Returns:
        LangChain StructuredTool instance

    """
    tool_name = tool_config.get("name", "unnamed_tool")
    tool_description = tool_config.get("description", "No description provided")
    endpoint = tool_config.get("endpoint", "")
    method = tool_config.get("method", "GET").upper()
    auth_config = tool_config.get("auth_config", {})
    verify_ssl = tool_config.get("verify_ssl", True)  # Default to True for security
    parameters_schema = tool_config.get(
        "parameters", {"type": "object", "properties": {}},
    )

    # Create dynamic input model from parameters schema
    input_model = _create_dynamic_input_model(tool_name, parameters_schema)

    async def mcp_api_call(**kwargs) -> str:
        """Execute the MCP API call with provided parameters."""
        logger.info(f"MCP tool '{tool_name}' called with params: {kwargs}")
        try:
            # Build authentication headers
            headers = _build_auth_headers(auth_config)
            headers["Content-Type"] = "application/json"

            logger.info(f"Making {method} request to {endpoint}")

            # Make HTTP request with configurable SSL verification
            async with httpx.AsyncClient(timeout=30.0, verify=verify_ssl) as client:
                if method in ["GET", "DELETE"]:
                    response = await client.request(
                        method=method, url=endpoint, headers=headers, params=kwargs,
                    )
                else:  # POST, PUT, PATCH
                    response = await client.request(
                        method=method, url=endpoint, headers=headers, json=kwargs,
                    )

                response.raise_for_status()

                # Try to return JSON, fallback to text
                try:
                    result = str(response.json())
                    logger.info(f"MCP tool '{tool_name}' succeeded: {result[:200]}")
                    return result
                except Exception:
                    result = response.text
                    logger.info(f"MCP tool '{tool_name}' succeeded (text): {result[:200]}")
                    return result

        except httpx.HTTPError as e:
            error_msg = f"MCP tool '{tool_name}' HTTP error: {e!s}"
            logger.exception(error_msg)
            return f"Error: {error_msg}"
        except Exception as e:
            error_msg = f"MCP tool '{tool_name}' failed: {e!s}"
            logger.exception(error_msg)
            return f"Error: {error_msg}"

    # Create StructuredTool with dynamic schema
    tool = StructuredTool(
        name=tool_name,
        description=tool_description,
        coroutine=mcp_api_call,
        args_schema=input_model,
    )

    logger.info(f"Created MCP tool: name='{tool_name}', description='{tool_description}', schema={input_model.model_json_schema()}")
    return tool


async def load_mcp_tools(
    session: AsyncSession, search_space_id: int,
) -> list[StructuredTool]:
    """Load all MCP tools from user's active MCP connectors.

    Args:
        session: Database session
        search_space_id: User's search space ID

    Returns:
        List of LangChain StructuredTool instances

    """
    try:
        # Fetch all MCP connectors for this search space
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.MCP_CONNECTOR,
                SearchSourceConnector.search_space_id == search_space_id,
            ),
        )

        tools: list[StructuredTool] = []
        for connector in result.scalars():
            # Each connector can define multiple tools in config
            config = connector.config or {}
            tool_configs = config.get("tools", [])

            for tool_config in tool_configs:
                try:
                    tool = await _create_mcp_tool_instance(tool_config, connector.id)
                    tools.append(tool)
                    logger.info(
                        f"Loaded MCP tool '{tool_config.get('name')}' from connector {connector.id}",
                    )
                except Exception as e:
                    logger.exception(
                        f"Failed to create MCP tool from connector {connector.id}: {e!s}",
                    )

        logger.info(f"Loaded {len(tools)} MCP tools for search space {search_space_id}")
        return tools

    except Exception as e:
        logger.exception(f"Failed to load MCP tools: {e!s}")
        return []
