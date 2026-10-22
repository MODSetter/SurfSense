# Server API and the turn

2.x's routes live under `/api`, wrap a reply as `{data}`, a list as `{data, cursor}` and an error as `{_tag, message}`. A request names its folder with `location[directory]=` (deepObject) or `x-opencode-directory`; a route about a session finds the folder from the session. The contract is [`protocol/openapi.json`](https://github.com/anomalyco/opencode/blob/v2.1.2/packages/protocol/openapi.json). As today, only [`opencode_client/`](../../../surfsense_local/backend/modules/agent/opencode_client/) speaks it.

## Routes

| SurfSense today (1.x) | 2.x |
|---|---|
| `GET /global/health` | `GET /api/info`, unwrapped: `{version, pid, urls, paths}` |
| `GET /config` | `GET /api/config` with the location: one entry per source, the file's as `{type: "document", path, info}` with `info` normalised |
| `POST /global/dispose` | not needed: the file is watched and reloads in about 0.3 s. `POST /api/location/reload` exists, and drops every MCP server added at runtime |
| `POST /instance/dispose` | `DELETE /api/debug/location`, which also drops the folder's MCP servers |
| `POST /session?directory=` `{title}` | `POST /api/session` `{title, agent, model: {providerID, id}, location: {directory}, permissions}` |
| `GET /session/:id`, `PATCH` `{metadata}` | the same under `/api`; the folder is `data.location.directory`; metadata is still replaced whole |
| `PATCH /session/:id` `{permission: [...]}` | `{permissions: [{action, resource, effect}]}`, which **replaces** the set and is read before every step |
| `GET /session?directory=` | `GET /api/session?directory=`, 50 per page, followed by `cursor.next` |
| `GET /session/status` | `GET /api/session/active`: only running sessions, as `{type: "running"}` |
| `GET /session/:id/message` | `GET /api/session/:id/message?order=asc&limit=200`, then by cursor |
| `POST /session/:id/prompt_async` `{agent, model, parts}` | `POST /api/session/:id/model` and `/agent` when they change, notes through `POST /api/session/:id/synthetic` with `resume: false`, then `POST /api/session/:id/prompt` `{id: "msg_…", text}`. A note is delivered first, as its own user message |
| `POST /session/:id/abort` | `POST /api/session/:id/interrupt` → `{interrupted}` |
| `POST /permission/:rid/reply` `{reply}` | `POST /api/session/:sid/permission/:rid/reply` `{decision}` |
| `POST /mcp?directory=` | `PUT /api/experimental/mcp/:name` with the location ([plugins](05-plugins.md)) |
| `GET /mcp`, `POST /mcp/:name/disconnect` | `GET /api/mcp` with the location, a list whose `status` is an object; `DELETE /api/experimental/mcp/:name` |

The MCP routes that add and remove a server are the only experimental routes SurfSense uses: opencode's API audit files them as "Experimental-only", a runtime override outside the stable API ([`V2_HTTP_API_AUDIT.md`](https://github.com/anomalyco/opencode/blob/v2.1.2/V2_HTTP_API_AUDIT.md)). They are used on purpose ([plugins](05-plugins.md#registration)). Migration progress is not read from `/api/experimental/migration/v1`: a known 1.x session answering `404` is retried briefly instead ([migration](07-migration-and-rollout.md#existing-threads)).

## Events

`GET /api/event` is one stream for every folder. It opens with `server.connected`, sends `: heartbeat` comments every 15 s, and frames carry `{id, created, type, location, data}` with no `id:` line, so nothing is replayed; after a reconnect the client reads messages and active sessions again. The silence timeout moves from 20 s to about 40 s.

| 1.x | 2.x ([`schema/src/session-event.ts`](https://github.com/anomalyco/opencode/blob/v2.1.2/packages/schema/src/session-event.ts)) |
|---|---|
| `message.updated` for the user | `session.inbox.enqueued`, then `session.inbox.delivered` |
| `message.updated` for the assistant | `session.step.started`, `session.step.ended`, `session.step.failed` |
| text and reasoning parts and deltas | `session.text.started/delta/ended`, `session.reasoning.*`, keyed by `(assistantMessageID, ordinal)` |
| a tool part | `session.tool.input.started/ended`, `session.tool.called`, `session.tool.success {content, metadata}`, `session.tool.failed {error}` |
| `permission.asked` `{permission, patterns, metadata.command, tool.callID}` | `{action, resources, metadata.input, source.id}`, where `source.id` is the tool call |
| `session.idle`, `session.error`, `session.status` | not sent: a turn ends with `session.execution.succeeded`, `.failed {error}` or `.interrupted {reason}` |
| `server.instance.disposed` | `location.shutdown` |
| `todo.updated` | none |

## Messages

A message is one tagged object: `user`, `synthetic`, `assistant`, `compaction`, `idle` and more ([`schema/src/session-message.ts`](https://github.com/anomalyco/opencode/blob/v2.1.2/packages/schema/src/session-message.ts)). An assistant message holds `content[]` of text, reasoning and tool items; a tool item's `id` is the call id and its `state` is `streaming`, `running`, `completed {content[]}` or `error {error}`. There is no `parentID`: a turn is a `user` message up to the next `idle {outcome}`. A compaction is its own message with its `summary`, and an overflow is recovered by compaction rather than surfacing an error.

What follows for the readers:

- [`turn_frames.py`](../../../surfsense_local/backend/modules/agent/agent_threads/turn_frames.py), [`replies.py`](../../../surfsense_local/backend/modules/agent/agent_threads/replies.py), [`steps.py`](../../../surfsense_local/backend/modules/agent/agent_threads/steps.py) and [`compaction.py`](../../../surfsense_local/backend/modules/agent/agent_threads/compaction.py) move to these shapes. A tool's output is its text content items joined; `title` is gone.
- An error is `{type, message, response.body}`: `aborted` for a stop, `provider.*` for the model, `permission.rejected` for a decline.
- A decline ends the turn with `execution.interrupted {reason: "shutdown"}` and no `idle` message, so [`recorded_endings.py`](../../../surfsense_local/backend/modules/agent/agent_threads/recorded_endings.py) keeps recording how a turn ended.
- Notes are `synthetic` messages, so [`scope_note.py`](../../../surfsense_local/backend/modules/agent/agent_threads/scope_note.py) finds them by type instead of a `synthetic` flag on a text part.
- The Claude Code engine converts its events into the shape these readers take ([`opencode_shape.py`](../../../surfsense_local/backend/modules/agent/engines/claude_code/opencode_shape.py), [`transcript_shape.py`](../../../surfsense_local/backend/modules/agent/engines/claude_code/transcript_shape.py)), so it moves with them.

## The model endpoint's requests

opencode now sends `x-session-affinity`, `x-session-id`, `x-opencode-session` and `x-opencode-session-id`, all the session id, and `max_completion_tokens` from the model's `limit.output`. It sends no `tool_choice`.
