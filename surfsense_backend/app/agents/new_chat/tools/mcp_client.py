"""MCP Client Wrapper.

This module provides a client for communicating with MCP servers via stdio and HTTP transports.
It handles server lifecycle management, tool discovery, and tool execution.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 1.0  # seconds
RETRY_BACKOFF = 2.0  # exponential backoff multiplier


class MCPClient:
    """Client for communicating with an MCP server."""

    def __init__(
        self, command: str, args: list[str], env: dict[str, str] | None = None
    ):
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
    async def connect(self, max_retries: int = MAX_RETRIES):
        """Connect to the MCP server and manage its lifecycle.

        Args:
            max_retries: Maximum number of connection retry attempts

        Yields:
            ClientSession: Active MCP session for making requests

        Raises:
            RuntimeError: If all connection attempts fail

        """
        last_error = None
        delay = RETRY_DELAY

        for attempt in range(max_retries):
            try:
                # Merge env vars with current environment
                server_env = os.environ.copy()
                server_env.update(self.env)

                # Create server parameters with env
                server_params = StdioServerParameters(
                    command=self.command, args=self.args, env=server_env
                )

                # Spawn server process and create session
                # Note: Cannot combine these context managers because ClientSession
                # needs the read/write streams from stdio_client
                async with stdio_client(server=server_params) as (read, write):  # noqa: SIM117
                    async with ClientSession(read, write) as session:
                        # Initialize the connection
                        await session.initialize()
                        self.session = session

                        if attempt > 0:
                            logger.info(
                                "Connected to MCP server on attempt %d: %s %s",
                                attempt + 1,
                                self.command,
                                " ".join(self.args),
                            )
                        else:
                            logger.info(
                                "Connected to MCP server: %s %s",
                                self.command,
                                " ".join(self.args),
                            )
                        yield session
                        return  # Success, exit retry loop

            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    logger.warning(
                        "MCP server connection failed (attempt %d/%d): %s. Retrying in %.1fs...",
                        attempt + 1,
                        max_retries,
                        e,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    delay *= RETRY_BACKOFF  # Exponential backoff
                else:
                    logger.error(
                        "Failed to connect to MCP server after %d attempts: %s",
                        max_retries,
                        e,
                        exc_info=True,
                    )
            finally:
                self.session = None

        # All retries exhausted
        error_msg = f"Failed to connect to MCP server '{self.command}' after {max_retries} attempts"
        if last_error:
            error_msg += f": {last_error}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from last_error

    async def list_tools(self) -> list[dict[str, Any]]:
        """List all tools available from the MCP server.

        Returns:
            List of tool definitions with name, description, and input schema

        Raises:
            RuntimeError: If not connected to server

        """
        if not self.session:
            raise RuntimeError(
                "Not connected to MCP server. Use 'async with client.connect():'"
            )

        try:
            # Call tools/list RPC method
            response = await self.session.list_tools()

            tools = []
            for tool in response.tools:
                tools.append(
                    {
                        "name": tool.name,
                        "description": tool.description or "",
                        "input_schema": tool.inputSchema
                        if hasattr(tool, "inputSchema")
                        else {},
                    }
                )

            logger.info("Listed %d tools from MCP server", len(tools))
            return tools

        except Exception as e:
            logger.error("Failed to list tools from MCP server: %s", e, exc_info=True)
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
            raise RuntimeError(
                "Not connected to MCP server. Use 'async with client.connect():'"
            )

        try:
            logger.info(
                "Calling MCP tool '%s' with arguments: %s", tool_name, arguments
            )

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
            logger.info("MCP tool '%s' succeeded: %s", tool_name, result_str[:200])
            return result_str

        except RuntimeError as e:
            # Handle validation errors from MCP server responses
            # Some MCP servers (like server-memory) return extra fields not in their schema
            if "Invalid structured content" in str(e):
                logger.warning(
                    "MCP server returned data not matching its schema, but continuing: %s",
                    e,
                )
                # Try to extract result from error message or return a success message
                return "Operation completed (server returned unexpected format)"
            raise
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error(
                "Failed to call MCP tool '%s': %s", tool_name, e, exc_info=True
            )
            return f"Error calling tool: {e!s}"


async def test_mcp_connection(
    command: str, args: list[str], env: dict[str, str] | None = None
) -> dict[str, Any]:
    """Test connection to an MCP server via stdio and fetch available tools.

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
    except (RuntimeError, ConnectionError, TimeoutError, OSError) as e:
        return {
            "status": "error",
            "message": f"Failed to connect: {e!s}",
            "tools": [],
        }


async def test_mcp_http_connection(
    url: str, headers: dict[str, str] | None = None, transport: str = "streamable-http"
) -> dict[str, Any]:
    """Test connection to an MCP server via HTTP and fetch available tools.

    Args:
        url: URL of the MCP server
        headers: Optional HTTP headers for authentication
        transport: Transport type ("streamable-http", "http", or "sse")

    Returns:
        Dict with connection status and available tools

    """
    try:
        logger.info(
            "Testing HTTP MCP connection to: %s (transport: %s)", url, transport
        )

        # Use streamable HTTP client for all HTTP-based transports
        async with (
            streamablehttp_client(url, headers=headers or {}) as (read, write, _),
            ClientSession(read, write) as session,
        ):
            await session.initialize()

            # List available tools
            response = await session.list_tools()
            tools = []
            for tool in response.tools:
                tools.append(
                    {
                        "name": tool.name,
                        "description": tool.description or "",
                        "input_schema": tool.inputSchema
                        if hasattr(tool, "inputSchema")
                        else {},
                    }
                )

            logger.info("HTTP MCP connection successful. Found %d tools.", len(tools))
            return {
                "status": "success",
                "message": f"Connected successfully. Found {len(tools)} tools.",
                "tools": tools,
            }

    except Exception as e:
        logger.error("Failed to connect to HTTP MCP server: %s", e, exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to connect: {e!s}",
            "tools": [],
        }
