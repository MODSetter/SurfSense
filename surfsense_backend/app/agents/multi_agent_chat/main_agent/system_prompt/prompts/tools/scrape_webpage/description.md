- `scrape_webpage` — Fetch and extract readable content from a single URL.
  - Use when the user wants the actual page body (article, table, dashboard
    snapshot), not just search snippets.
  - Try the tool when a URL is given or referenced; don't refuse without
    attempting unless the URL is clearly unsafe or invalid.
  - Public web only. For URLs behind a connector (Notion pages, Linear
    issues, Confluence, anything that needs auth), use `task` with the
    matching specialist instead.
  - Args: `url`, `max_length` (default 50000).
  - Returns title, metadata, and markdown-ish body. Summarise clearly and
    link back with `[label](url)`.
