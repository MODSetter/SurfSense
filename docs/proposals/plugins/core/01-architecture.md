# Architecture

> Owns: `surfsense_local/backend/modules/plugins/` (`gateway/`, `installed/`, `results/`, `routes.py`), the plugin tables. The MCP client is [`../remote/01-mcp-client.md`](../remote/01-mcp-client.md)'s, the copy of the registry [`02-registry.md`](02-registry.md)'s.
> Callers: [`03-engines.md`](03-engines.md). Sources: [`../remote/README.md`](../remote/README.md), later [`bundles/`](../bundles/README.md).

## Shape

```
opencode ──MCP──► modules/agent/plugin_tools ──┐
chat engine ──► modules/chat/plugin_router ────┼──► Tool Gateway ──► ToolSource ──► remote MCP server
"@plugin tool" in the composer ────────────────┘         │                       (later: bundle process)
                                                          ├── Installed: what is connected, enabled, ready
                                                          ├── Policy and approval
                                                          └── plugin_calls: every call and its result
```

The app owns one tool pipeline that every call passes through, and MCP is a source of tools adapted into it, as in Pi ([README](../README.md#prior-art)). No plugin code runs inside the app. The app is an MCP client towards plugin servers and, for opencode, an MCP server in front of the gateway ([`03-engines.md`](03-engines.md#opencode)); both sides are plain MCP.

## The Tool Gateway

`modules/plugins/gateway/` is the only door to a plugin tool. Two calls:

| Call | Returns |
|---|---|
| `list_tools(scope) -> list[PluginTool]` | The tools ready in this workspace: plugin connected and enabled, Restricted mode allowing it, credentials present, its hosts allowed, the tool itself on. A paid plugin's license is not checked here: its server decides ([`05-paid.md`](05-paid.md)) |
| `call_tool(scope, name, arguments, caller) -> ToolOutcome` | Checks the arguments against the tool's schema, asks for approval when its policy says so ([`04-trust.md`](04-trust.md)), records a `plugin_calls` row, calls the source, trims the result, stores it, returns it |

`scope` carries the workspace, the thread, and the turn. `caller` is `agent`, `chat_router` or `mention`. A refusal (no credentials, a host revoked, a server refusing the license, the user denying) comes back as a `ToolOutcome` with a sentence the model or the screen shows, never an exception.

`PluginTool` is engine-neutral: the qualified name, the plugin's display name, the tool's title and description, its input schema, its MCP annotations, its exposure. `exposure` is SurfSense's, not MCP's: `direct` (listed to the engines) or `deferred` (later, found by search, [`06-later.md`](06-later.md)), stored per tool, `direct` by default. Each caller turns it into what its engine needs ([`03-engines.md`](03-engines.md)).

## Tool sources

A source is anything that can list and call tools:

```python
class ToolSource(Protocol):
    async def list_tools(self) -> list[SourceTool]: ...
    async def call_tool(self, name: str, arguments: dict, *, cancel: CancelToken) -> SourceResult: ...
```

- `RemoteMcpSource` (`mcp_client/`) is the first, one per connected remote plugin ([`../remote/README.md`](../remote/README.md)).
- `BundleSource` comes with bundles: the same interface over a local process ([`bundles/`](../bundles/README.md)).

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
| `installed_plugins` | `id`, `kind` (`remote`), `source` (`registry` or `custom`), `url`, `publisher`, `enabled`, `connected_at`, the registry entry it was connected from |
| `plugin_credentials` | `plugin_id`, `kind` (`oauth`, `token`, `license`), encrypted values through `shared/secrets.py`: token, refresh token, expiry, the registered OAuth client |
| `plugin_tools` | `plugin_id`, `tool`, `first_seen_at`, `enabled`, `approval` (`ask` or `always`, [`04-trust.md`](04-trust.md#approval)), `exposure`, and the description, annotations and schema last seen, which [`02-registry.md`](02-registry.md#tools-added-later) compares on each listing |
| `plugin_calls` | `id`, `workspace_id`, `thread_id`, `message_id`, `caller`, `plugin_id`, `tool`, `arguments`, `status` (`waiting_approval`, `running`, `succeeded`, `failed`, `denied`, `cancelled`), `result_text`, `result_data`, `error`, `started_at`, `finished_at` |

`plugin_runs`, built for the earlier design, stays for bundles.

## Routes

| Method | Path | Does |
|---|---|---|
| `GET` | `/plugins` | The registry joined with what is installed: each plugin's entry, publisher, access, connection state, the server's last refusal if any, tools and their switches |
| `POST` | `/plugins/registry/refresh` | Fetches the registry again ([`02-registry.md`](02-registry.md#how-the-app-gets-the-registry)) |
| `POST` | `/plugins/{id}/connect` | Starts connecting: a token, OAuth, or the license, after egress consent |
| `POST` | `/plugins/custom` | Adds a remote server by URL |
| `DELETE` | `/plugins/{id}` | Disconnects: credentials deleted, tools gone; past calls stay in their threads |
| `PUT` | `/plugins/{id}/tools/{tool}` | Turns a tool on or off and sets its approval |
| `PUT` | `/plugins/restricted-mode` | Turns third-party plugins on or off |
| `GET` | `/plugins/{id}/calls` | The plugin's recent calls, for its activity view |
| `POST` | `/workspaces/{id}/plugin-calls/{call}/save` | Saves a result to Sources ([`03-engines.md`](03-engines.md#save-to-sources)) |

Approval answers go through the thread's existing permission route ([`04-trust.md`](04-trust.md#approval)).

## Acceptance

- A fake source registered in a test lists its tools through `list_tools` only when its plugin is connected, enabled, and its hosts allowed; disconnecting removes them.
- `call_tool` with arguments that break the schema returns a refusal and writes no call.
- A 60 KB text result reaches the caller trimmed with its marker, and `plugin_calls` holds all 60 KB.
- Two plugins whose names collide after sanitising get distinct qualified names.
- A source that raises during a call ends the call `failed` with the reason, and the caller gets a sentence, not an error.
