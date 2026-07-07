# SurfSense MCP Server

A [Model Context Protocol](https://modelcontextprotocol.io/) server that exposes
SurfSense to MCP clients like **Claude Code**, **Cursor**, and **Claude Desktop**.
It talks to a running SurfSense backend purely over its REST API using a SurfSense
API key — it imports no backend code and can point at any instance (local or
hosted) by changing two environment variables.

## Tools

**Search-space selector**
- `surfsense_list_workspaces` — list the workspaces (search spaces) you can access
- `surfsense_select_workspace` — pick the active workspace by name or id

**Scrapers (all platforms)**
- `surfsense_web_crawl`, `surfsense_google_search`, `surfsense_reddit_scrape`,
  `surfsense_youtube_scrape`, `surfsense_youtube_comments`,
  `surfsense_google_maps_scrape`, `surfsense_google_maps_reviews`
- `surfsense_list_scraper_runs`, `surfsense_get_scraper_run` — retrieve past
  results in full (useful when a large result was truncated inline)

**Knowledge base**
- `surfsense_search_knowledge_base` — semantic + keyword search over stored content
- `surfsense_list_documents`, `surfsense_get_document`
- `surfsense_add_document`, `surfsense_upload_file`
- `surfsense_update_document`, `surfsense_delete_document`

Workspace-scoped tools default to the active workspace; pass `workspace` (a name
or id) to override for a single call. Ids never need to be typed by hand — the
model carries them between calls.

## Prerequisites

1. A running SurfSense backend (default `http://localhost:8000`).
2. A **SurfSense API key**: SurfSense → Settings → API → create key (`ss_pat_…`).
3. **API access enabled** on the workspace(s) you want to use (workspace settings).

## Setup

Uses [uv](https://github.com/astral-sh/uv):

```bash
cd surfsense_mcp
uv sync
uv run python -m surfsense_mcp.selfcheck   # verify tools register correctly
```

## Connect it to a client

### Cursor

Add to `~/.cursor/mcp.json` (or a project `.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "surfsense": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/SurfSense/surfsense_mcp", "python", "-m", "surfsense_mcp"],
      "env": {
        "SURFSENSE_BASE_URL": "http://localhost:8000",
        "SURFSENSE_API_KEY": "ss_pat_your_token_here"
      }
    }
  }
}
```

### Claude Code

```bash
claude mcp add surfsense \
  -e SURFSENSE_BASE_URL=http://localhost:8000 \
  -e SURFSENSE_API_KEY=ss_pat_your_token_here \
  -- uv run --directory /absolute/path/to/SurfSense/surfsense_mcp python -m surfsense_mcp
```

### Claude Desktop

Add the same `mcpServers` block as Cursor to
`claude_desktop_config.json` (Settings → Developer → Edit Config).

## Configuration

See `.env.example`. Secrets are passed as environment variables by the client;
never commit tokens.

## Backend dependency

`surfsense_search_knowledge_base` calls `POST /api/v1/documents/search-semantic`,
a thin endpoint that exposes the backend's existing hybrid retriever over REST.
All other tools use pre-existing SurfSense endpoints.
