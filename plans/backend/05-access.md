# Phase 5 — Access / Surfaces (REST · MCP · chat doors)

> Build after `04`. Together `04 + 05` ship the scraper-API product.
> Reuses shipped infra: Identity/Tenancy, API keys, the chat agent + tool registry, the streaming layer,
> Metering (`03c`), and Rocicorp Zero reactive sync. Locate code by symbol/grep.

## Objective

Expose the `04` capability registry through three doors — REST + API keys, an MCP server, and chat tools —
each generated from the one registry so the I/O contract can't drift. Every door is the same thin adapter
with no business logic.

## Adapter shape (identical on every door)

```
parse input → validate against verb.input_schema → authn/authz → meter-gate (03c)
  → call the SAME executor (04) → serialize verb.output_schema → return cleaned data
```

The executor returns directly (`04`).

## The three doors

| Door | Who | Auth | Status |
|------|-----|------|--------|
| REST + API keys | external developers | existing API-key infra | public day one |
| MCP server | external agents (Cursor/ChatGPT/Claude) | OAuth 2.1 or bearer (at implementation) | fast-follow |
| Chat tools | the in-app agent (`07`) | existing session + workspace | seed exists (`scrape_webpage`) |

Routes are generated, so public REST on day one costs nothing extra.

## Chat surface

The in-app product is the conversation: the user describes a need in plain language and the agent (`07`)
picks and fills verbs. Raw typed verbs are exposed on REST/MCP for devs and external agents. The chat
door classifies intent and routes:

```
"find / compare / what is / pull / right now"          → ONE-SHOT      → call verbs, answer now
"watch / track / notify me / keep an eye / over time"  → KEEP-WATCHING → hand to the ongoing mode (06)
```

## MCP — two directions

- **Serve MCP** (new door): our capabilities as a remote MCP server — Streamable-HTTP `/mcp`, stateless,
  bounded/paginated outputs, read-only verbs (least privilege).
- **Consume MCP** (reuse): the BYO-`MCP_CONNECTOR` — the user's own external MCP tools inside our chat
  agent. Fix its routing-map gap here.

## Result delivery

A chat tool call returns its data inline in the turn. Asynchronous results (e.g. the `06` ongoing mode
writing between turns) reach the client via write-then-sync / stream: the worker writes rows and the
client receives them over the existing SSE stream or a Zero-published table.

## Work items

1. Door generator: from the `04` registry emit (a) REST routes + models, (b) MCP tool schemas + handlers,
   (c) chat tool defs + handlers.
2. REST surface: public routes + API-key auth (reuse) + `03c` meter-gate.
3. Chat tools: generalize `scrape_webpage` into the registry-backed set (direct-return).
4. Intent routing: classify one-shot vs keep-watching; hand keep-watching to `06`.
5. MCP server (fast-follow): Streamable-HTTP `/mcp`, least-privilege; auth depth at implementation.
6. Consume-MCP fix: repair the BYO-`MCP_CONNECTOR` routing-map gap.

## Tests

- A verb added to the registry appears on REST + MCP + chat with identical I/O.
- REST without a valid key → 401; an over-budget call → blocked by the `03c` gate; a success charges once.
- A chat scrape returns cleaned data inline in the same turn.
- "compare X and Y" → one-shot; "watch X weekly" → routed to `06`.
- A configured BYO MCP tool is reachable by the chat agent.

## Out of scope

- Verbs, executors, billing units → `04`.
- Keep-watching mechanism + its delivery channel → `06`.
- The CI subagent + its prompt → `07`.
- Legacy branded connectors (backward-compat hygiene, separate task).

## Open questions

- MCP auth depth (decide at implementation).
- Public REST rate-limiting / abuse posture.
- Async delivery channel for `06` outputs: SSE stream vs Zero-published messages table (settled with `06`).
