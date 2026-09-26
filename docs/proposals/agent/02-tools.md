# The agent's tools

> Both engines reach the user's sources through one small set of SurfSense functions. opencode calls them over MCP; fixed workflows call them in process.

## What exists today

- **Search.** `retrieve(session, workspace_id, query, top_k=5, document_ids=None) -> list[Hit]` in [`shared/search.py`](../../../surfsense_local/backend/shared/search.py). Chat is its only caller ([`modules/chat/router.py`](../../../surfsense_local/backend/modules/chat/router.py)). It does not filter by document type, so artifacts, which are documents ([ADR 0003](../../adr/0003-artifacts-as-documents.md)), come back with sources.
- **Full text.** Each document's extracted markdown is stored in `documents.content` ([data model](../../architecture/data-model.md)). No route returns a document's body ([documents](../../architecture/documents.md), Known gaps). Ingestion also writes `extracted.md` beside each uploaded file ([`worker/ingestion/parsing.py`](../../../surfsense_local/backend/worker/ingestion/parsing.py)); no code reads it back.
- **Around a citation.** `GET /workspaces/{id}/documents/by-chunk/{chunk_id}?chunk_window=5` returns a chunk with up to five neighbours on each side ([chat](../../architecture/chat.md), Citation panel).
- **Studio's grounding.** Studio reads `documents.content` for the selected documents, capped at 24,000 characters in selection order ([`gather.py`](../../../surfsense_local/backend/worker/studio/shared/gather.py); [studio](../../architecture/studio.md), Known gaps).
- **Creating an artifact.** `create_artifact_job(session, workspace, payload, *, tool_call_id=None)` in [`modules/artifacts/service.py`](../../../surfsense_local/backend/modules/artifacts/service.py). Its docstring: "the REST route passes no tool_call_id, a future create_artifact tool passes its own. Nothing else differs."

## Tools to add

| Tool | Returns | Built on |
|---|---|---|
| `search_sources` | ranked passages with document id, title and chunk id | `retrieve()`, with a document-type filter added |
| `read_source` | one page of a document's extracted markdown | `documents.content` |
| `read_around_citation` | a chunk with its neighbours | the query behind the by-chunk route |
| `list_sources` | id, title and type of each ready document | the documents list route |
| `create_artifact` | the new artifact's id | `create_artifact_job(..., tool_call_id=...)` |

- **To opencode:** an MCP server on loopback. At `v1.18.32`, opencode accepts a remote MCP server by URL with static `headers`, and `"oauth": false` turns OAuth off ([`core/src/v1/config/mcp.ts`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/core/src/v1/config/mcp.ts)).
- **To workflows:** plain function calls in the worker.

The desktop backend has no MCP library ([`uv.lock`](../../../surfsense_local/backend/uv.lock)). The separate `surfsense_mcp` server depends on `mcp>=1.26.0` ([`surfsense_mcp/pyproject.toml`](../../../surfsense_mcp/pyproject.toml)).

## Open questions

- Whether `search_sources` returns artifacts, which would let the agent cite its own earlier output.
- The paging unit for `read_source`: characters, chunks, or the line ranges chunks already carry.
- Which MCP library the desktop backend takes, and whether it freezes with PyInstaller ([packaging](../../architecture/packaging.md)).
- How the loopback MCP server authenticates opencode. Loopback routes have no auth today, which the [plugins proposal](../plugins/README.md) accepts for plugins.
