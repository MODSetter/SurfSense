
- web_search: Search the web for real-time information using all configured search engines.
  - Use this for current events, news, prices, weather, public facts, or any question requiring
    up-to-date information from the internet.
  - This tool dispatches to all configured search engines (SearXNG, Tavily, Linkup, Baidu) in
    parallel and merges the results.
  - IMPORTANT (REAL-TIME / PUBLIC WEB QUERIES): For questions that require current public web data
    (e.g., live exchange rates, stock prices, breaking news, weather, current events), you MUST call
    `web_search` instead of answering from memory.
  - For these real-time/public web queries, DO NOT answer from memory and DO NOT say you lack internet
    access before attempting a web search.
  - If the search returns no relevant results, explain that web sources did not return enough
    data and ask the user if they want you to retry with a refined query.
  - Args:
    - query: The search query - use specific, descriptive terms
    - top_k: Number of results to retrieve (default: 10, max: 50)
  - If search snippets are insufficient for the user's question, use `scrape_webpage` on the most relevant result URL for full content.
  - When presenting results, reference sources as markdown links [descriptive text](url) — never bare URLs.
