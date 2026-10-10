# Architecture

> Owns: `surfsense_local/backend/modules/plugins/` (`gateway/`, `installed/`, `results/`, `routes.py`), the plugin tables. `remote/` is [`../remote/01-mcp-client.md`](../remote/01-mcp-client.md)'s, `lists/` [`02-registry.md`](02-registry.md)'s, `bundles/` [`../bundles/`](../bundles/README.md)'s.
> Callers: [`03-engines.md`](03-engines.md). Sources: [`../remote/README.md`](../remote/README.md), later [`bundles/`](../bundles/README.md).

## Shape

```
opencode ──MCP──► modules/agent/plugin_tools ──┐
"@plugin tool" in the agent composer ──────────┼──► Tool Gateway ──► ToolSource ──► remote MCP server
chat engine, later ──► plugin_router ──────────┘         │                       (later: bundle process)
                                                          ├── Installed: what is connected, enabled, ready
                                                          ├── Policy and approval
                                                          └── plugin_calls: every call and its result
```

The app owns one tool pipeline that every call passes through, and MCP is a source of tools adapted into it, as in Pi ([README](../README.md#prior-art)). No plugin code runs inside the app. The app is an MCP client towards plugin servers and, for opencode, an MCP server in front of the gateway ([`03-engines.md`](03-engines.md#opencode)); both sides are plain MCP.

## Layout

```
surfsense_local/backend/modules/plugins/
  routes.py          the /plugins routes, the same for every kind
  gateway/           the only door to a tool: list_tools, call_tool, ToolSource, names, trimming, approval
  installed/         what is connected: installed_plugins, credentials, tool switches
  results/           plugin_calls, Save to Sources
  lists/             where plugins come from, every kind (02-registry.md)
    first_party/     SurfSense's plugins: plugins.json and icons/, packaged into the app
    registry/        third-party plugins: fetch, signature check, cache
  remote/            the remote kind (../remote/01-mcp-client.md)
    mcp_client/      Streamable HTTP: initialize, tools/list, tools/call, cancel, progress
    sign_in/         token, OAuth and its callback route, the License header
    source.py        RemoteMcpSource
  bundles/           the bundle kind, deferred: the earlier design's runner, later BundleSource
```

What every kind shares sits at the top, in folders named for what they do. Each kind is one folder that plugs into the gateway through a `ToolSource`, so a new kind adds a folder and changes nothing above it.

## The Tool Gateway

`modules/plugins/gateway/` is the only door to a plugin tool. Two calls:

| Call | Returns |
|---|---|
| `list_tools(scope) -> list[PluginTool]` | The tools ready in this workspace: plugin connected and enabled, third-party plugins allowed if it is one, credentials present, its hosts allowed, the tool itself on. A paid plugin's license is not checked here: its server decides ([`05-paid.md`](05-paid.md)) |
| `call_tool(scope, name, arguments, caller) -> ToolOutcome` | Checks the arguments against the tool's schema, asks for approval when its policy says so ([`04-trust.md`](04-trust.md)), records a `plugin_calls` row, calls the source, trims the result, stores it, returns it |

`scope` carries the workspace, the thread, and the turn. `caller` is `agent` or `mention`; `chat_router` is kept for the chat engine's router step, later ([`03-engines.md`](03-engines.md#the-chat-engine-later)). A refusal (no credentials, a host revoked, a server refusing the license, the user denying) comes back as a `ToolOutcome` with a sentence the model or the screen shows, never an exception.

`PluginTool` is engine-neutral: the qualified name, the plugin's display name, the tool's title and description, its input schema, its MCP annotations, its exposure. `exposure` is SurfSense's, not MCP's: `direct` (listed to the engines) or `deferred` (later, found by search, [`06-later.md`](06-later.md)), stored per tool, `direct` by default. Each caller turns it into what its engine needs ([`03-engines.md`](03-engines.md)).

## Tool sources

A source is anything that can list and call tools:

```python
class ToolSource(Protocol):
    async def list_tools(self) -> list[SourceTool]: ...
    async def call_tool(self, name: str, arguments: dict, *, cancel: CancelToken) -> SourceResult: ...
```

- `RemoteMcpSource`, in `remote/source.py` over `remote/mcp_client/`, is the first, one per connected remote plugin ([`../remote/README.md`](../remote/README.md)).
- `BundleSource`, in `bundles/`, comes with bundles: the same interface over a local process ([`bundles/`](../bundles/README.md)).

Nothing above the gateway knows which kind of source a tool came from.

## Names

A tool's qualified name is `<plugin id>__<tool name>`, with every character outside `[A-Za-z0-9_]` replaced by `_`, cut to 55 characters with a short hash when longer. opencode adds its server prefix, so the agent sees `plugins_notion__search`, and the prefix still fits within the 64 characters providers allow. Permissions, steps, history and `@` mentions all use the qualified name.

## Results

- A source returns MCP content: text, images, and `structuredContent` when the server sends it.
- Text over 20 KB reaches a model with its middle removed and a marker saying how much was cut. The full result is kept with the call.
- Results are kept in `plugin_calls` and shown as a step of the turn ([`03-engines.md`](03-engines.md#results)).

## Tables

Hand-written migrations, as [ADR 0005](../../../adr/0005-hand-written-migrations.md) requires.

| Table | Holds |
|---|---|
| `installed_plugins` | `id`, `kind` (`remote`), `source` (`first_party`, `registry` or `custom`), `url` (unique: one plugin per server, stored in one spelling, with scheme and host lowercased and no default port, trailing slash or fragment), `publisher`, `enabled`, `connected_at`, the list entry it was connected from, and its sign-in: `credential_kind` and `credential_ciphertext`, encrypted through `shared/secrets.py`, as `provider_connections` keeps a connection's key |
| `plugin_tools` | `plugin_id`, `tool`, `position` (the server's order), `first_seen_at`, `enabled`, `approval` (`ask` or `always`, [`04-trust.md`](04-trust.md#approval)), `exposure`, and the description, annotations and schema last seen, which [`02-registry.md`](02-registry.md#tools-added-later) compares on each listing |
| `plugin_calls` | `id`, `workspace_id`, `thread_id`, `message_id`, `caller`, `plugin_id`, `tool`, `arguments`, `status` (`waiting_approval`, `running`, `succeeded`, `failed`, `denied`, `cancelled`), `result_text`, `result_data`, `error`, `started_at`, `finished_at` |
| `plugin_settings` | One row: `third_party_on`, whether the user allowed third-party plugins ([`02-registry.md`](02-registry.md#third-party-plugins)) |

A tool is a row, not an entry in a JSON list on its plugin: each carries the user's switch and approval, the gateway finds ready tools and one tool by name in a query, and tool search needs an index over rows. Its schema and annotations, always read whole, are JSON within the row. LobeChat keeps a row per tool with its permission, as here.

Added later, each with the feature that needs it, without changing these tables:

- an FTS5 index, and a sqlite-vec one for search by meaning, over each tool's name, title and description, for finding tools beyond the 24 a thread lists ([`06-later.md`](06-later.md));
- an index on `plugin_calls (workspace_id, thread_id)`, once reopening a thread reads many calls;
- a fingerprint of a plugin's last listing, so a listing that changed nothing skips the comparison;
- the sign-in's expiry, with OAuth, so tokens refresh before they lapse.

`plugin_runs`, built for the earlier design, stays for bundles, with its runner in `modules/plugins/bundles/`.

## Routes

| Method | Path | Does |
|---|---|---|
| `GET` | `/plugins` | The first-party list and, once third-party plugins are allowed, the registry, joined with what is installed: each plugin's entry, publisher, access, connection state, the server's last refusal if any, tools and their switches |
| `POST` | `/plugins/registry/refresh` | Fetches the registry again ([`02-registry.md`](02-registry.md#how-the-app-gets-the-registry)) |
| `POST` | `/plugins/{id}/connect` | Starts connecting: a token, OAuth, or the license, after egress consent |
| `POST` | `/plugins/custom` | Adds a remote server by URL |
| `DELETE` | `/plugins/{id}` | Disconnects: credentials deleted, tools gone; past calls stay in their threads |
| `PUT` | `/plugins/{id}/tools/{tool}` | Turns a tool on or off and sets its approval |
| `PUT` | `/plugins/third-party` | Allows or refuses third-party plugins |
| `GET` | `/plugins/{id}/calls` | The plugin's recent calls, for its activity view |
| `POST` | `/workspaces/{id}/plugin-calls/{call}/save` | Saves a result to Sources ([`03-engines.md`](03-engines.md#save-to-sources)) |

Approval answers go through the thread's existing permission route ([`04-trust.md`](04-trust.md#approval)).

## Acceptance

- A fake source registered in a test lists its tools through `list_tools` only when its plugin is connected, enabled, and its hosts allowed; disconnecting removes them.
- `call_tool` with arguments that break the schema returns a refusal and writes no call.
- A 60 KB text result reaches the caller trimmed with its marker, and `plugin_calls` holds all 60 KB.
- Two plugins whose names collide after sanitising get distinct qualified names.
- A source that raises during a call ends the call `failed` with the reason, and the caller gets a sentence, not an error.
