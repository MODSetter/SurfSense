# The agent's tools

> Both engines reach the user's sources through one small set of SurfSense functions. Fixed workflows call them in process. opencode calls the two it cannot do with files, searching and creating an artifact, over MCP, and reads everything else from its text view.

## What exists today

- **Search.** `retrieve(session, workspace_id, query, top_k=5, document_ids=None) -> list[Hit]` in [`shared/search.py`](../../../surfsense_local/backend/shared/search.py). Chat ([`modules/chat/router.py`](../../../surfsense_local/backend/modules/chat/router.py)) and Studio's grounding ([`gather.py`](../../../surfsense_local/backend/worker/studio/shared/gather.py)) call it. It does not filter by document type, so artifacts, which are documents ([ADR 0003](../../adr/0003-artifacts-as-documents.md)), come back with sources.
- **Full text.** Each document's extracted markdown is stored in `documents.content` ([data model](../../architecture/data-model.md)). No route returns a document's body ([documents](../../architecture/documents.md), Known gaps).
- **Around a citation.** `GET /workspaces/{id}/documents/by-chunk/{chunk_id}?chunk_window=5` returns a chunk with up to five neighbours on each side ([chat](../../architecture/chat.md), Citation panel).
- **Studio's grounding.** Studio reads `documents.content` for the selected documents, capped at 24,000 characters in selection order ([`gather.py`](../../../surfsense_local/backend/worker/studio/shared/gather.py); [studio](../../architecture/studio.md), Known gaps).
- **Creating an artifact.** `create_artifact_job(session, workspace, payload, *, tool_call_id=None)` in [`modules/artifacts/service.py`](../../../surfsense_local/backend/modules/artifacts/service.py). Its docstring: "the REST route passes no tool_call_id, a future create_artifact tool passes its own. Nothing else differs."

## Tools to add

| Tool | Returns | Built on |
|---|---|---|
| `search_sources` | ranked passages, each labelled with its chunk id, its file in the text view and its lines there | `retrieve()`, scoped by id to the ready files and notes |
| `read_source` | one page of a document's extracted markdown | `documents.content` |
| `read_around_citation` | a chunk with its neighbours | the query behind the by-chunk route |
| `list_sources` | id, title and type of each ready document | the documents list route |
| `create_artifact` | that the job started; the artifact appears in Studio | `create_artifact_job()` |

- **To opencode:** `search_sources` and `create_artifact`, over an MCP server on loopback. opencode reads the text view with its own `read`, `grep` and `glob` ([`03-opencode.md`](03-opencode.md), Working folders), so the other three would repeat them, and every tool sent costs context (the same file, Fixed prompt size).
- **To workflows:** all five, as plain function calls in the worker.

How opencode reaches them, as built ([agent](../../architecture/agent.md#surfsenses-tools)):

- At `v1.18.34`, opencode accepts a remote MCP server by URL with static `headers`, and `"oauth": false` turns OAuth off ([`core/src/v1/config/mcp.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/core/src/v1/config/mcp.ts)). The key made at each opencode launch goes in `headers`, and the server refuses a request without it. A remote server rather than a local one keeps opencode from starting an MCP process that inherits its environment.
- One URL per workspace, added to the turn's working folder before each turn with `POST /mcp?directory=…`. A tool call names neither its folder nor its session, and opencode keeps a server added this way in memory for that folder alone, losing it on every reload ([`opencode/src/mcp/index.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/mcp/index.ts)). The configuration file holds none, because every folder reads the same one.
- No MCP library. The endpoint answers the four requests opencode's client sends, `initialize`, `tools/list`, `tools/call` and `ping`, stateless and JSON only. The official Python SDK's high-level server also declares resources, which opencode turns into three more tools that only denying `read` would hide; its stateless `GET` holds a stream open, so opencode's SSE fallback waits out its 30-second connect timeout; it needs the host app's lifespan; and it would add 7 to 9 packages to the frozen API.
- Tool schemas are flat, with no `$ref` or `$defs`. Small local models send the arguments of a referenced schema as a string ([#52390](https://github.com/anomalyco/opencode/issues/52390)), and Pydantic emits `$defs` for nested models, so the schemas are written out flat.
- `search_sources` labels each passage with its chunk id, which stays unique across every search of a session, where a chat answer's `[1]` to `[5]` would not. The agent's prompt asks it to cite those labels; the backend reads them back from the session's search results and rewrites the reply with the chat's `resolve_citations()`, so an agent answer carries citations the way a chat answer does, and a label no search returned is dropped ([chat](../../architecture/chat.md)).
- `search_sources` searches only the ready files and notes the text view holds. An artifact is the agent's output, not a source.

## Open questions

- The paging unit for `read_source`: characters, chunks, or the line ranges chunks already carry.
