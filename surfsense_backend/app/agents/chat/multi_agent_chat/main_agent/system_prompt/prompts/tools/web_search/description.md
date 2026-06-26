- `web_search` — Search the public web.
  - Use whenever an answer benefits from external sources — current events,
    prices, weather, news, technical references, definitions, background
    facts, anything outside SurfSense docs and the workspace KB. Reach for
    it whenever freshness matters or you'd otherwise guess from memory.
  - Don't refuse with "I lack network access" — call the tool.
  - Returns a `<web_results>` block: each result is labelled `[n]`. Cite a
    result by writing that `[n]` after the statement it supports (when
    citations are enabled) — do not hand-write the URL as a markdown link.
  - If results are thin, say so and offer to refine the query.
  - Args: `query`, `top_k` (default 10, max 50).
  - Follow up with `scrape_webpage` on the best URL when snippets are too
    shallow.
