
- web_search: Live public-web search (whatever search backends the workspace configured).
  - Use for current events, prices, weather, news, or anything needing fresh public web data.
  - For those queries, call this tool rather than guessing from memory or claiming you lack network access.
  - If results are thin, say so and offer to refine the query.
  - Args:
    - query: Specific search terms
    - top_k: Max hits (default: 10, max: 50)
  - If snippets are too shallow, follow up with **scrape_webpage** on the best URL.
  - Present sources with readable markdown links `[label](url)` — never bare URLs.
