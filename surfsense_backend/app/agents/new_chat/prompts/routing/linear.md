<linear_routing>
**Linear:** Prefer the `task` tool with subagent **`linear_specialist`** when the user’s request is **only about Linear** and may need several tool calls (list issues, inspect one issue, teams, users, statuses, comments, documents). Use **`connector_negotiator`** when Linear is one hop in a **multi-connector** workflow. Call Linear MCP tools directly from the parent when a **single** quick call is enough.
</linear_routing>
