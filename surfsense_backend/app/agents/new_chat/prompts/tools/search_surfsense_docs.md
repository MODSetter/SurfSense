
- search_surfsense_docs: Search the official SurfSense documentation.
  - Use this tool when the user asks anything about SurfSense itself (the application they are using).
  - Args:
    - query: The search query about SurfSense
    - top_k: Number of documentation chunks to retrieve (default: 10)
  - Returns: Documentation content with chunk IDs for citations (prefixed with 'doc-', e.g., [citation:doc-123])
