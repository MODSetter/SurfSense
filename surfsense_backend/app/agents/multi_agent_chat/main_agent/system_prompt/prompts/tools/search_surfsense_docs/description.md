- `search_surfsense_docs` — Search official SurfSense documentation (product
  help).
  - Use when the user asks how SurfSense itself works — setup, configuration,
    connector documentation, feature behavior, anything covered in the
    product docs.
  - Not a substitute for `task` when the user wants actions inside a
    connected service (Gmail, Slack, Jira, Notion, etc.).
  - Args: `query`, `top_k` (default 10).
  - Returns doc excerpts; chunk ids may appear for attribution — see
    `<citations>` for the contract.
