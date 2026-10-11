# Architecture

> Owns: `surfsense_local/backend/modules/plugins/` (`gateway/`, `installed/`, `routes.py`), the plugin tables. `remote/` is [`../remote/01-mcp-client.md`](../remote/01-mcp-client.md)'s, `lists/` [`02-registry.md`](02-registry.md)'s, `bundles/` [`../bundles/`](../bundles/README.md)'s.
> Callers: [`03-engines.md`](03-engines.md): the agent's opencode through its own MCP client, the chat engine later through the gateway. Sources: [`../remote/README.md`](../remote/README.md), later [`bundles/`](../bundles/README.md).

## Shape

```
                each turn: ready servers, sign-in as headers, a rule per tool
SurfSense ──────────────────────────────────────────────────────► opencode ──MCP──► remote MCP server
   │  ◄──────────── opencode's tool steps, read back to show the thread ───┘  │ TLS through
   │                                                                          │ SurfSense's proxy:
   ├── Proxy: tunnels only to a ready plugin's host ◄─────────────────────────┘ host checked, content not seen
   ├── Installed: what is connected, enabled, ready
   ├── Policy and approval: which tools each caller gets, which ask
   └── Tool Gateway ──► ToolSource ──► remote MCP server       chat engine, later; SurfSense's own checks
                                       (later: bundle process)
```

SurfSense decides, in one place, which plugin tools each caller gets and which must be approved. No plugin code runs inside the app. The agent's opencode is an MCP client already, so it calls the plugin servers SurfSense gives each turn itself, under the rules SurfSense writes, and SurfSense stays out of the call's path but for the TLS tunnel its proxy opens to a ready plugin's host ([`03-engines.md`](03-engines.md#opencode)). SurfSense's own callers, the chat engine later and the listing checks it runs, reach servers through the Tool Gateway, where MCP is a source of tools adapted into one pipeline, as in Pi ([README](../README.md#prior-art)). Both sides speak plain MCP.

## Layout

```
surfsense_local/backend/modules/plugins/
  routes.py          the /plugins routes, the same for every kind
  gateway/           readiness and approval rules, and the door to a tool for SurfSense's own callers
  installed/         what is connected: installed_plugins, credentials, tool switches
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

`modules/plugins/gateway/` decides which plugin tools are ready and which must be approved. Each turn gives the agent's opencode what it decides ([`03-engines.md`](03-engines.md#each-turn)).

| Call | Returns |
|---|---|
| `list_tools(session) -> list[ReadyTool]` | The tools ready now: plugin connected and enabled, third-party plugins allowed if it is one, its hosts allowed, the tool itself on, in the order their plugins were connected and their servers listed them. A paid plugin's license is not checked here: its server decides ([`05-paid.md`](05-paid.md)) |
| `needs_approval(tool) -> bool` | Whether each call of the tool must be approved, from its annotations, where its plugin comes from, and the user's setting ([`04-trust.md`](04-trust.md#approval)) |

`ReadyTool` is engine-neutral: the qualified name, the plugin's id, display name and source, the tool's title and description, its input schema, its MCP annotations, its approval setting and its exposure. `exposure` is SurfSense's, not MCP's: `direct` (given to the engines) or `deferred` (later, found by search, [`06-later.md`](06-later.md)), stored per tool, `direct` by default.

The gateway calls no tool today: the agent's opencode calls plugin servers itself. Calling a tool through the gateway, for SurfSense's own callers, comes with the chat engine ([`03-engines.md`](03-engines.md#the-chat-engine-later)).

## Tool sources

A source is anything that can list tools, as the gateway records them:

```python
class ToolSource(Protocol):
    async def list_tools(self) -> list[SourceTool]: ...
```

- `RemoteMcpSource`, in `remote/source.py` over `remote/mcp_client/`, is the first, one per connected remote plugin ([`../remote/README.md`](../remote/README.md)).
- `BundleSource`, in `bundles/`, comes with bundles: the same interface over a local process ([`bundles/`](../bundles/README.md)).

The chat engine adds calling to the interface when it needs it. Nothing above the gateway knows which kind of source a tool came from.

## Names

A tool's qualified name is `<plugin id>__<tool name>`, with every character outside `[A-Za-z0-9_]` replaced by `_`, cut to 55 characters with a short hash when longer, and kept distinct when two plugins' names collide. The agent's names are opencode's: it prefixes each tool with the server name SurfSense gives it, the plugin's id, so the agent sees `notion_search`, and opencode's rules and steps name tools that way.

## Results

The agent's results are opencode's: each call, its arguments and its result are kept in the thread's opencode session, which SurfSense already reads to show the thread ([`03-engines.md`](03-engines.md#results)). SurfSense keeps no copy. The chat engine, which has no session of that kind, brings a table of its calls with it ([`03-engines.md`](03-engines.md#the-chat-engine-later)).

## Tables

Hand-written migrations, as [ADR 0005](../../../adr/0005-hand-written-migrations.md) requires.

| Table | Holds |
|---|---|
| `installed_plugins` | `id`, `kind` (`remote`), `source` (`first_party`, `registry` or `custom`), `url` (unique: one plugin per server, stored in one spelling, with scheme and host lowercased and no default port, trailing slash or fragment), `publisher`, `enabled`, `connected_at`, the list entry it was connected from, and its sign-in: `credential_kind` and `credential_ciphertext`, encrypted through `shared/secrets.py`, as `provider_connections` keeps a connection's key |
| `plugin_tools` | `plugin_id`, `tool`, `position` (the server's order), `first_seen_at`, `enabled`, `approval` (`ask` or `always`, [`04-trust.md`](04-trust.md#approval)), `exposure`, and the description, annotations and schema last seen, which [`02-registry.md`](02-registry.md#tools-added-later) compares on each listing |
| `plugin_settings` | One row: `third_party_on`, whether the user allowed third-party plugins ([`02-registry.md`](02-registry.md#third-party-plugins)) |

A tool is a row, not an entry in a JSON list on its plugin: each carries the user's switch and approval, the gateway finds ready tools and one tool by name in a query, and tool search needs an index over rows. Its schema and annotations, always read whole, are JSON within the row. LobeChat keeps a row per tool with its permission, as here.

Added later, each with the feature that needs it, without changing these tables:

- an FTS5 index, and a sqlite-vec one for search by meaning, over each tool's name, title and description, for finding tools beyond the 24 a thread lists ([`06-later.md`](06-later.md));
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
| `DELETE` | `/plugins/{id}` | Disconnects: the sign-in and the tools go; past calls stay in their threads' sessions |
| `PUT` | `/plugins/{id}` | Switches a plugin off or on. Off pauses it: its sign-in and tool settings stay, and none of its tools reach a caller |
| `PUT` | `/plugins/{id}/tools/{tool}` | Turns a tool on or off and sets its approval |
| `PUT` | `/plugins/third-party` | Allows or refuses third-party plugins |
| `GET` | `/plugins/{id}/calls` | The plugin's recent calls in agent threads, read from their sessions, for its activity view |
| `POST` | `/chat/threads/{thread}/plugin-steps/{step}/save` | Saves a plugin step's result to Sources ([`03-engines.md`](03-engines.md#save-to-sources)) |

In agent threads approval is opencode's own request, asked on its step in the reply and answered on the thread's existing permission route ([`04-trust.md`](04-trust.md#approval)), so the plugin routes need none of their own.

## Acceptance

- A fake source registered in a test lists its tools through `list_tools` only when its plugin is connected, enabled, and its hosts allowed; disconnecting removes them.
- A third-party plugin's tools are listed only once third-party plugins are allowed.
- Two plugins whose names collide after sanitising get distinct qualified names.
- `needs_approval` follows [`04-trust.md`](04-trust.md#approval): a first-party read-only tool runs, a third party's asks, Always allow covers a tool that is not destructive, and a destructive tool, or one with no annotations, always asks.
