"""Composition root: build the MCP server and wire in every feature slice.

Creates the REST transport and workspace context from settings, then lets each
feature register its tools on the server.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .config import Settings
from .core.client import SurfSenseClient
from .core.workspace_context import WorkspaceContext
from .features import knowledge_base, scrapers, workspaces


def build_server(settings: Settings) -> tuple[FastMCP, SurfSenseClient]:
    """Assemble a configured server and the client whose lifecycle it shares."""
    client = SurfSenseClient(
        api_base=settings.api_base, pat=settings.pat, timeout=settings.timeout
    )
    context = WorkspaceContext(client, preferred_reference=settings.default_workspace)

    mcp = FastMCP("SurfSense")
    workspaces.register(mcp, context)
    scrapers.register(mcp, client, context)
    knowledge_base.register(mcp, client, context)
    return mcp, client
