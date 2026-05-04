
- scrape_webpage: Fetch and extract readable content from a single HTTP(S) URL.
  - Use when the user wants the *actual page body* (article, table, dashboard snapshot), not just search snippets.
  - Try the tool when a URL is given or referenced; don’t refuse without attempting unless the URL is clearly unsafe/invalid.
  - Args:
    - url: Page to fetch
    - max_length: Cap on returned characters (default: 50000)
  - Returns: Title, metadata, and markdown-ish body.
  - Summarize clearly afterward; link back with `[label](url)`.
  - If indexed workspace material is insufficient and the user points at a public URL, scraping is appropriate — still not a substitute for **task** on private connectors.
