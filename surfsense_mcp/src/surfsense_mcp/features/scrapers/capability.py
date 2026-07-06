"""Run a SurfSense scraper capability and shape its result.

Shared by every platform tool: POST a typed payload to the workspace's scraper
door and render the returned items as markdown or JSON.
"""

from __future__ import annotations

from typing import Any

from ...core.client import SurfSenseClient
from ...core.rendering import ResponseFormat, clip, to_json
from ...core.workspace_context import WorkspaceContext


async def run_scraper(
    client: SurfSenseClient,
    context: WorkspaceContext,
    *,
    platform: str,
    verb: str,
    payload: dict[str, Any],
    workspace: str | None,
    response_format: ResponseFormat,
) -> str:
    """Execute one scraper verb for the resolved workspace and render its output."""
    resolved = await context.resolve(workspace)
    body = {key: value for key, value in payload.items() if value is not None}
    result = await client.request(
        "POST", f"/workspaces/{resolved.id}/scrapers/{platform}/{verb}", json=body
    )
    if response_format == "json":
        return clip(to_json(result))
    return _render_markdown(platform, verb, resolved.name, result)


def _render_markdown(
    platform: str, verb: str, workspace_name: str, result: Any
) -> str:
    """A readable header plus the structured payload, clipped to a safe size."""
    header = f'# {platform}.{verb} — {_describe_size(result)} from "{workspace_name}"'
    body = clip(to_json(result))
    return f"{header}\n\n```json\n{body}\n```"


def _describe_size(result: Any) -> str:
    if isinstance(result, dict) and isinstance(result.get("items"), list):
        return f"{len(result['items'])} item(s)"
    return "result"
