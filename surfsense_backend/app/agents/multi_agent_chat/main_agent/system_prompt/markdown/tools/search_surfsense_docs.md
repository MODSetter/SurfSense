
- search_surfsense_docs: Search official SurfSense documentation (product help).
  - Use when the user asks how SurfSense works, setup, connectors at a high level, configuration, etc.
  - Not a substitute for **task** when they need actions inside Gmail/Slack/Jira/etc.
  - Args:
    - query: What to look up in SurfSense docs
    - top_k: Number of chunks to retrieve (default: 10)
  - Returns: Doc excerpts; chunk ids may appear for attribution — follow the **citation**
    instructions block above when citations are enabled; otherwise summarize without `[citation:…]`.
