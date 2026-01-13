"""MCP Client Wrapper.

This module provides a client for communicating with MCP servers via stdio transport.
It handles server lifecycle management, tool discovery, and tool execution.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

logger = logging.getLogger(__name__)


class MCPClient:
    """Client for communicating with an MCP server."""

    def __init__(self, command: str, args: list[str], env: dict[str, str] | None = None):
        """Initialize MCP client.

        Args:
            command: Command to spawn the MCP server (e.g., "uvx", "node")
            args: Arguments for the command (e.g., ["mcp-server-git"])
            env: Optional environment variables for the server process

        """
        self.command = command
        self.args = args
        self.env = env or {}
        self.session: ClientSession | None = None

    @asynccontextmanager
    async def connect(self):
        """Connect to the MCP server and manage its lifecycle.

        Yields:
            ClientSession: Active MCP session for making requests

        """
        try:
            # Merge env vars with current environment
            server_env = os.environ.copy()
            server_env.update(self.env)
            
            # Create server parameters with env
            server_params = StdioServerParameters(
                command=self.command,
                args=self.args,
                env=server_env
            )
            
            # Spawn server process and create session
            async with stdio_client(server=server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    # Initialize the connection
                    await session.initialize()
                    self.session = session
                    logger.info(
                        f"Connected to MCP server: {self.command} {' '.join(self.args)}"
                    )
                    yield session

        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e!s}", exc_info=True)
            raise
        finally:
            self.session = None
            logger.info(f"Disconnected from MCP server: {self.command}")

    async def list_tools(self) -> list[dict[str, Any]]:
        """List all tools available from the MCP server.

        Returns:
            List of tool definitions with name, description, and input schema

        Raises:
            RuntimeError: If not connected to server

        """
        if not self.session:
            raise RuntimeError("Not connected to MCP server. Use 'async with client.connect():'")

        try:
            # Call tools/list RPC method
            response = await self.session.list_tools()

            tools = []
            for tool in response.tools:
                tools.append({
                    "name": tool.name,
                    "description": tool.description or "",
                    "input_schema": tool.inputSchema if hasattr(tool, "inputSchema") else {},
                })

            logger.info(f"Listed {len(tools)} tools from MCP server")
            return tools

        except Exception as e:
            logger.error(f"Failed to list tools from MCP server: {e!s}", exc_info=True)
            raise

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Call a tool on the MCP server.

        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool

        Returns:
            Tool execution result

        Raises:
            RuntimeError: If not connected to server

        """
        if not self.session:
            raise RuntimeError("Not connected to MCP server. Use 'async with client.connect():'")

        try:
            logger.info(f"Calling MCP tool '{tool_name}' with arguments: {arguments}")

            # Call tools/call RPC method
            response = await self.session.call_tool(tool_name, arguments=arguments)

            # Extract content from response
            result = []
            for content in response.content:
                if hasattr(content, "text"):
                    result.append(content.text)
                elif hasattr(content, "data"):
                    result.append(str(content.data))
                else:
                    result.append(str(content))

            result_str = "\n".join(result) if result else ""
            logger.info(f"MCP tool '{tool_name}' succeeded: {result_str[:200]}")
            return result_str

        except RuntimeError as e:
            # Handle validation errors from MCP server responses
            # Some MCP servers (like server-memory) return extra fields not in their schema
            if "Invalid structured content" in str(e):
                logger.warning(f"MCP server returned data not matching its schema, but continuing: {e}")
                # Try to extract result from error message or return a success message
                return "Operation completed (server returned unexpected format)"
            raise
        except Exception as e:
            logger.error(f"Failed to call MCP tool '{tool_name}': {e!s}", exc_info=True)
            return f"Error calling tool: {e!s}"


async def test_mcp_connection(
    command: str, args: list[str], env: dict[str, str] | None = None
) -> dict[str, Any]:
    """Test connection to an MCP server and fetch available tools.

    Args:
        command: Command to spawn the MCP server
        args: Arguments for the command
        env: Optional environment variables

    Returns:
        Dict with connection status and available tools

    """
    client = MCPClient(command, args, env)

    try:
        async with client.connect():
            tools = await client.list_tools()
            return {
                "status": "success",
                "message": f"Connected successfully. Found {len(tools)} tools.",
                "tools": tools,
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to connect: {e!s}",
            "tools": [],
        }
