"""MCP Tool Factory.

This module creates LangChain tools from MCP servers using the Model Context Protocol.
Tools are dynamically discovered from MCP servers - no manual configuration needed.

This implements real MCP protocol support similar to Cursor's implementation.
"""

import logging
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, create_model
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.tools.mcp_client import MCPClient
from app.db import SearchSourceConnector, SearchSourceConnectorType

logger = logging.getLogger(__name__)


def _normalize_gemini_params(params: dict[str, Any], mcp_schema: dict[str, Any]) -> dict[str, Any]:
    """Normalize Gemini-transformed parameter names back to MCP schema format.
    
    Gemini tends to transform field names like:
    - entityType -> type
    - from/to -> fromEntity/toEntity
    - relationType -> relation
    
    This function maps them back to the original MCP schema field names.
    """
    schema_properties = mcp_schema.get("properties", {})
    normalized = {}
    
    for param_key, param_value in params.items():
        # Handle array parameters (need to normalize nested objects)
        if isinstance(param_value, list) and len(param_value) > 0:
            if isinstance(param_value[0], dict):
                # Get the items schema to know what fields should be present
                items_schema = schema_properties.get(param_key, {}).get("items", {})
                items_properties = items_schema.get("properties", {})
                
                normalized_array = []
                for item in param_value:
                    normalized_item = {}
                    for item_key, item_value in item.items():
                        # Map common Gemini transformations back to MCP names
                        if item_key == "type" and "entityType" in items_properties:
                            normalized_item["entityType"] = item_value
                        elif item_key == "fromEntity" and "from" in items_properties:
                            normalized_item["from"] = item_value
                        elif item_key == "toEntity" and "to" in items_properties:
                            normalized_item["to"] = item_value
                        elif item_key == "relation" and "relationType" in items_properties:
                            normalized_item["relationType"] = item_value
                        else:
                            # Use the original key if it exists in schema
                            normalized_item[item_key] = item_value
                    
                    # Add missing required fields with empty defaults if needed
                    for required_field in items_properties.keys():
                        if required_field not in normalized_item:
                            # For arrays like observations, default to empty array
                            if items_properties[required_field].get("type") == "array":
                                normalized_item[required_field] = []
                            else:
                                normalized_item[required_field] = ""
                    
                    normalized_array.append(normalized_item)
                normalized[param_key] = normalized_array
            else:
                normalized[param_key] = param_value
        else:
            normalized[param_key] = param_value
    
    return normalized


def _create_dynamic_input_model_from_schema(
    tool_name: str, input_schema: dict[str, Any],
) -> type[BaseModel]:
    """Create a Pydantic model from MCP tool's JSON schema.

    Args:
        tool_name: Name of the tool (used for model class name)
        input_schema: JSON schema from MCP server

    Returns:
        Pydantic model class for tool input validation

    """
    properties = input_schema.get("properties", {})
    required_fields = input_schema.get("required", [])

    # Build Pydantic field definitions
    field_definitions = {}
    for param_name, param_schema in properties.items():
        param_description = param_schema.get("description", "")
        is_required = param_name in required_fields
        
        # Use Any type for complex schemas to preserve structure
        # This allows the MCP server to do its own validation
        from typing import Any as AnyType
        from pydantic import Field
        
        if is_required:
            field_definitions[param_name] = (AnyType, Field(..., description=param_description))
        else:
            field_definitions[param_name] = (
                AnyType | None,
                Field(None, description=param_description),
            )

    # Create dynamic model
    model_name = f"{tool_name.replace(' ', '').replace('-', '_')}Input"
    return create_model(model_name, **field_definitions)


async def _create_mcp_tool_from_definition(
    tool_def: dict[str, Any],
    mcp_client: MCPClient,
) -> StructuredTool:
    """Create a LangChain tool from an MCP tool definition.

    Args:
        tool_def: Tool definition from MCP server with name, description, input_schema
        mcp_client: MCP client instance for calling the tool

    Returns:
        LangChain StructuredTool instance

    """
    tool_name = tool_def.get("name", "unnamed_tool")
    tool_description = tool_def.get("description", "No description provided")
    input_schema = tool_def.get("input_schema", {"type": "object", "properties": {}})

    # Log the actual schema for debugging
    logger.info(f"MCP tool '{tool_name}' input schema: {input_schema}")

    # Create dynamic input model from schema
    input_model = _create_dynamic_input_model_from_schema(tool_name, input_schema)

    async def mcp_tool_call(**kwargs) -> str:
        """Execute the MCP tool call via the client."""
        logger.info(f"MCP tool '{tool_name}' called with params: {kwargs}")
        
        # Normalize Gemini-transformed field names back to MCP schema
        # Gemini transforms: entityType->type, from/to->fromEntity/toEntity, relationType->relation
        normalized_kwargs = _normalize_gemini_params(kwargs, input_schema)
        
        try:
            # Connect to server and call tool
            async with mcp_client.connect():
                result = await mcp_client.call_tool(tool_name, normalized_kwargs)
                return str(result)
        except Exception as e:
            error_msg = f"MCP tool '{tool_name}' failed: {e!s}"
            logger.exception(error_msg)
            return f"Error: {error_msg}"

    # Create StructuredTool with response_format to preserve exact schema
    tool = StructuredTool(
        name=tool_name,
        description=tool_description,
        coroutine=mcp_tool_call,
        args_schema=input_model,
        # Store the original MCP schema as metadata so we can access it later
        metadata={"mcp_input_schema": input_schema},
    )

    logger.info(f"Created MCP tool: '{tool_name}'")
    return tool


async def load_mcp_tools(
    session: AsyncSession, search_space_id: int,
) -> list[StructuredTool]:
    """Load all MCP tools from user's active MCP server connectors.

    This discovers tools dynamically from MCP servers using the protocol.

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
            try:
                # Extract server config
                config = connector.config or {}
                server_config = config.get("server_config", {})

                command = server_config.get("command")
                args = server_config.get("args", [])
                env = server_config.get("env", {})

                if not command:
                    logger.warning(f"MCP connector {connector.id} missing command, skipping")
                    continue

                # Create MCP client
                mcp_client = MCPClient(command, args, env)

                # Connect and discover tools
                async with mcp_client.connect():
                    tool_definitions = await mcp_client.list_tools()

                    logger.info(
                        f"Discovered {len(tool_definitions)} tools from MCP server "
                        f"'{command}' (connector {connector.id})"
                    )

                    # Create LangChain tools from definitions
                    for tool_def in tool_definitions:
                        try:
                            tool = await _create_mcp_tool_from_definition(tool_def, mcp_client)
                            tools.append(tool)
                        except Exception as e:
                            logger.exception(
                                f"Failed to create tool '{tool_def.get('name')}' "
                                f"from connector {connector.id}: {e!s}",
                            )

            except Exception as e:
                logger.exception(
                    f"Failed to load tools from MCP connector {connector.id}: {e!s}",
                )

        logger.info(f"Loaded {len(tools)} MCP tools for search space {search_space_id}")
        return tools

    except Exception as e:
        logger.exception(f"Failed to load MCP tools: {e!s}")
        return []
