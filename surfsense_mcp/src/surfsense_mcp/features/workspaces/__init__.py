"""Search-space selector: discover workspaces and choose the active one.

A workspace (the product calls it a "search space") scopes every other tool.
These two tools let a client list what's available and pick one by name, so the
rest of the conversation needs no ids.
"""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from ...core.rendering import ResponseFormatParam, to_json
from ...core.workspace_context import Workspace, WorkspaceContext

_READ_ONLY = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)


def register(mcp: FastMCP, context: WorkspaceContext) -> None:
    """Register the workspace selector tools on the server."""

    @mcp.tool(
        name="surfsense_list_workspaces",
        title="List workspaces",
        annotations=_READ_ONLY,
        structured_output=False,
    )
    async def list_workspaces(
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """List the SurfSense workspaces (search spaces) the account can access.

        Use this to discover which workspaces exist before selecting one, or
        when the user asks what search spaces they have. Returns each
        workspace's name, id, description, ownership, and member count, and
        marks the currently active one.
        """
        workspaces = await context.fetch_all()
        if response_format == "json":
            return to_json([_as_dict(w) for w in workspaces])
        return _render_list(workspaces, active=context.active)

    @mcp.tool(
        name="surfsense_select_workspace",
        title="Select active workspace",
        annotations=_READ_ONLY,
        structured_output=False,
    )
    async def select_workspace(
        workspace: Annotated[
            str,
            Field(
                description="Workspace name or numeric id; matching is "
                "case-insensitive and a unique partial name works. "
                "Example: 'Research'."
            ),
        ],
    ) -> str:
        """Set the active workspace (search space) that later tools default to.

        Use this when the user says which search space to work in ("use my
        Research space"), or after surfsense_list_workspaces when several
        exist. Once set, workspace-scoped tools use it unless given a
        different 'workspace'. Do NOT call it before every tool — once per
        session is enough.
        """
        selected = await context.resolve(workspace)
        return (
            f"Active workspace is now '{selected.name}' (id {selected.id}). "
            "Other tools will use it unless you pass a different 'workspace'."
        )


def _render_list(workspaces: list[Workspace], *, active: Workspace | None) -> str:
    if not workspaces:
        return "No accessible workspaces."
    lines = ["# Workspaces", ""]
    for workspace in workspaces:
        marker = " — active" if active and active.id == workspace.id else ""
        role = "owner" if workspace.is_owner else "member"
        lines.append(f"- **{workspace.name}** (id {workspace.id}){marker}")
        if workspace.description:
            lines.append(f"  - {workspace.description}")
        lines.append(f"  - {role}, {workspace.member_count} member(s)")
    return "\n".join(lines)


def _as_dict(workspace: Workspace) -> dict:
    return {
        "id": workspace.id,
        "name": workspace.name,
        "description": workspace.description,
        "is_owner": workspace.is_owner,
        "member_count": workspace.member_count,
    }
