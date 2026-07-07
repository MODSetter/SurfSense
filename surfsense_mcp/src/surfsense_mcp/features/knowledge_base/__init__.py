"""Knowledge-base tools: search the KB and manage its documents.

Semantic search plus the document lifecycle — list, read, add text, upload a
file, update, and delete — over a workspace's knowledge base. Read tools live in
search_tools, mutations in document_tools.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ...core.client import SurfSenseClient
from ...core.workspace_context import WorkspaceContext
from . import document_tools, search_tools


def register(
    mcp: FastMCP, client: SurfSenseClient, context: WorkspaceContext
) -> None:
    """Register every knowledge-base tool on the server."""
    search_tools.register(mcp, client, context)
    document_tools.register(mcp, client, context)
