# SurfSense MCP Server

A [Model Context Protocol](https://modelcontextprotocol.io/) server that exposes
SurfSense to MCP clients like **Claude Code**, **Cursor**, and **Claude Desktop**.
It talks to a SurfSense backend purely over its REST API using a SurfSense API
key — it imports no backend code.

Connect it two ways:

- **Hosted** (recommended) — point your client at `https://mcp.surfsense.com/mcp`
  and pass your API key in a header. Nothing to install or keep running.
- **Self-host (stdio)** — run the server yourself against any backend (cloud or
  your own). Best for self-hosters and clients without remote-server support.

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

## Get an API key

1. SurfSense → **API Playground → API Keys**: create a personal key (`ss_pat_…`).
   It is shown only once.
2. Toggle **API key access** on for the workspace(s) you want to use.

## Connect (hosted)

Point your client at the hosted server and send the key as a Bearer token. For
clients that read an `mcpServers` map (Cursor, Claude Desktop, and others):

```json
{
  "mcpServers": {
    "surfsense": {
      "url": "https://mcp.surfsense.com/mcp",
      "headers": { "Authorization": "Bearer ss_pat_your_key_here" }
    }
  }
}
```

Claude Code, from a terminal:

```bash
claude mcp add --transport http surfsense https://mcp.surfsense.com/mcp \
  --header "Authorization: Bearer ss_pat_your_key_here"
```

Most MCP clients accept this `url` + `headers` form; check your client's docs for
its exact remote-server field.

## Self-host (stdio)

Run the server yourself when you host your own backend or use a client without
remote support. It uses [uv](https://github.com/astral-sh/uv):

```bash
cd surfsense_mcp
uv sync
uv run python -m mcp_server.selfcheck   # verify tools register correctly
```

Then add it to your client. Cursor (`~/.cursor/mcp.json` or a project
`.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "surfsense": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/SurfSense/surfsense_mcp", "python", "-m", "mcp_server"],
      "env": {
        "SURFSENSE_BASE_URL": "http://localhost:8000",
        "SURFSENSE_API_KEY": "ss_pat_your_token_here"
      }
    }
  }
}
```

Claude Code:

```bash
claude mcp add surfsense \
  -e SURFSENSE_BASE_URL=http://localhost:8000 \
  -e SURFSENSE_API_KEY=ss_pat_your_token_here \
  -- uv run --directory /absolute/path/to/SurfSense/surfsense_mcp python -m mcp_server
```

Claude Desktop: add the same `mcpServers` block as Cursor to
`claude_desktop_config.json` (Settings → Developer → Edit Config).

## Configuration

See `.env.example`. For self-host, secrets are passed as environment variables by
the client; never commit tokens.

## Backend dependency

`surfsense_search_knowledge_base` calls `POST /api/v1/documents/search-semantic`,
a thin endpoint that exposes the backend's existing hybrid retriever over REST.
All other tools use pre-existing SurfSense endpoints.
