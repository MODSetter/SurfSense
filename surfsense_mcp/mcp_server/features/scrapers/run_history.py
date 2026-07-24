"""Scraper run history: list past runs and fetch one in full.

A scrape whose inline result was truncated is retrievable here by run id, so the
model never re-runs a scraper just to recover output.
"""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ...core.client import SurfSenseClient
from ...core.rendering import ResponseFormatParam, clip, to_json
from ...core.workspace_context import WorkspaceContext, WorkspaceParam
from .annotations import READ_RUNS


def register(mcp: FastMCP, client: SurfSenseClient, context: WorkspaceContext) -> None:
    """Register the run-history tools."""

    @mcp.tool(
        name="surfsense_list_scraper_runs",
        title="List past scraper runs",
        annotations=READ_RUNS,
        structured_output=False,
    )
    async def list_scraper_runs(
        limit: Annotated[int, Field(ge=1, description="Maximum runs to list.")] = 20,
        capability: Annotated[
            str | None,
            Field(
                description="Filter by capability slug, e.g. 'web.crawl' or "
                "'reddit.scrape'."
            ),
        ] = None,
        status: Annotated[
            str | None,
            Field(description="Filter by run status: 'success' or 'error'."),
        ] = None,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """List recent scraper runs in the workspace, newest first.

        Use this to find the run_id of an earlier scrape — for example when an
        inline result was truncated — then fetch it in full with
        surfsense_get_scraper_run. Returns each run's id, capability, status,
        item count, and creation time.
        Example: capability='reddit.scrape', status='success'.
        """
        resolved = await context.resolve(workspace)
        runs = await client.request(
            "GET",
            f"/workspaces/{resolved.id}/scrapers/runs",
            params={
                "limit": limit,
                "capability": capability,
                "status": status,
            },
        )
        if response_format == "json":
            return to_json(runs)
        return _render_runs(runs)

    @mcp.tool(
        name="surfsense_get_scraper_run",
        title="Fetch one scraper run in full",
        annotations=READ_RUNS,
        structured_output=False,
    )
    async def get_scraper_run(
        run_id: Annotated[
            str,
            Field(
                description="Run id from surfsense_list_scraper_runs or a "
                "prior scrape's output."
            ),
        ],
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Fetch a single scraper run in full, including its stored output.

        Use this to retrieve the complete, untruncated result of an earlier
        scrape. Do NOT re-run a scraper just to recover a truncated result —
        fetch the stored run instead.
        """
        resolved = await context.resolve(workspace)
        run = await client.request(
            "GET", f"/workspaces/{resolved.id}/scrapers/runs/{run_id}"
        )
        if response_format == "json":
            return clip(to_json(run))
        return f"# Run {run.get('id', run_id)}\n\n```json\n{clip(to_json(run))}\n```"


def _render_runs(runs: list[dict] | None) -> str:
    if not runs:
        return "No scraper runs found."
    lines = ["# Scraper runs", ""]
    for run in runs:
        lines.append(
            f"- **{run.get('id')}** — {run.get('capability')} · {run.get('status')} · "
            f"{run.get('item_count', 0)} item(s) · {run.get('created_at')}"
        )
    return "\n".join(lines)
