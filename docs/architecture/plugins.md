# Plugins

A plugin is a remote MCP server whose tools the agent can use. The user connects one by its URL in Settings → Plugins, chooses which of its tools the agent may use and which ask first, and the agent's opencode calls the server itself, under rules SurfSense writes each turn ([agent](agent.md#plugins)). Only servers added by URL exist so far; SurfSense's own plugins, the third-party registry, sign-in with OAuth and plugins in Basic threads are still the [proposal](../proposals/plugins/README.md).

**Code:** [`surfsense_local/backend/modules/plugins/`](../../surfsense_local/backend/modules/plugins/), [`surfsense_local/frontend/src/features/plugins/`](../../surfsense_local/frontend/src/features/plugins/)
**Decisions:** [ADR 0051](../adr/0051-plugins-are-mcp-servers-behind-one-tool-gateway.md)

## Connecting a server

`POST /plugins/custom` with `{url, name, token?}`, in this order:

1. The URL is put in one spelling: scheme and host lowercased, no default port, trailing slash or fragment ([`server_url.py`](../../surfsense_local/backend/modules/plugins/installed/server_url.py)), so one server is never connected twice.
2. A name already in use is `409 plugin_name_taken`, and a server already connected is `409 plugin_already_connected`, each with `name`. A name becomes the id, lowercase words joined by hyphens; `surfsense` is never one, since it is the agent's own server.
3. A server off this computer not on HTTPS is `422 plugin_needs_https`: the agent reaches remote servers only through a TLS tunnel ([agent](agent.md#network)).
4. A host not allowed is `403 egress_disabled` with `hosts` and `purpose: "plugin"`, so the prompt words its question for a plugin's server, and the host is recorded off for Settings › Network ([egress](egress.md)).
5. SurfSense lists the server's tools with the official MCP SDK's client, the key as `Authorization: Bearer`. A `401` or `403` is `422 plugin_needs_sign_in`; anything else that fails is `502 plugin_unreachable`.
6. The plugin is stored with its key encrypted (`shared/secrets.py`), and every tool it listed starts on.

## Tables

| Table | Holds |
|---|---|
| `installed_plugins` | `id`, `kind` (`remote`), `source` (`first_party`, `registry` or `custom`), the unique `url`, `publisher`, the `entry` it was connected from, `enabled`, `connected_at`, and its key as `credential_kind` and `credential_ciphertext` |
| `plugin_tools` | one row per tool: its listing (`title`, `description`, `input_schema`, `annotations`), `position`, the user's `enabled` and `approval` (`ask` or `always`), `exposure`, `first_seen_at`; removed with its plugin |
| `plugin_settings` | one row: `third_party_on` |

## Ready tools

`list_tools()` in [`gateway/listing.py`](../../surfsense_local/backend/modules/plugins/gateway/listing.py) is the one answer to which tools may be used now: a tool switched on, of a plugin switched on, whose hosts are all allowed, and, unless SurfSense publishes it, only while third-party plugins are allowed. `needs_approval()` in [`gateway/approval.py`](../../surfsense_local/backend/modules/plugins/gateway/approval.py) says which ask: a first-party read-only tool never does, a tool that does not say it is read-only and does not say it is harmless (`destructiveHint` absent or true) always does, and any other asks unless set to Always allow.

**Tools added later.** Each listing after the first is recorded by [`recorded_tools.py`](../../surfsense_local/backend/modules/plugins/installed/recorded_tools.py): a new tool starts off, a tool whose description changed or whose annotations became less safe is switched off, and a tool the server dropped is deleted. The agent's turn lists again at most every five minutes ([agent](agent.md#plugins)).

## Routes

| Method | Path | Does |
|---|---|---|
| `GET` | `/plugins` | Every connected plugin with its tools; never a key |
| `POST` | `/plugins/custom` | Connects a server by URL, as above |
| `PUT` | `/plugins/{id}` | `{enabled}`: off pauses a plugin, keeping its key and tool settings |
| `PUT` | `/plugins/{id}/tools/{tool}` | `{enabled}` or `{approval}` |
| `GET` / `PUT` | `/plugins/third-party` | `{allowed}` |
| `DELETE` | `/plugins/{id}` | Disconnects: the key and the tools go; steps it took stay in their threads' sessions |

## Settings → Plugins

[`plugins-settings.tsx`](../../surfsense_local/frontend/src/features/plugins/plugins-settings.tsx), under System, says plugins work in Agentic threads and holds:

- **Allow third-party plugins**, off by default. Turning it on first asks, saying other people run those servers, what a tool is sent goes to its publisher, and SurfSense does not review changes to them. Turning it off asks nothing. While it is off, a custom plugin says "Not used until third-party plugins are allowed".
- **Add MCP server**, under MCP servers, a dialog with Name, Server URL and an optional Key. Each refusal above is shown in the app's words by its `code` ([`refusal-message.ts`](../../surfsense_local/frontend/src/features/plugins/refusal-message.ts)); a host not allowed raises the egress prompt and retries once allowed.
- **One card per plugin:** its name, "Third-party · host" or "By SurfSense · host", a switch that pauses it, and Disconnect, which asks first. Its tools are split into Read-only and Can make changes, each with a switch and, where the rules leave a choice, Ask or Always allow; a tool that always asks says "Always asks", and a first-party read-only one "Doesn’t ask" ([`tool-kind.ts`](../../surfsense_local/frontend/src/features/plugins/tool-kind.ts) mirrors `needs_approval()`).

## Tests

- **Backend:** [`tests/integration/plugins/routes/`](../../surfsense_local/backend/tests/integration/plugins/routes/) connect real MCP servers on loopback ([`tests/mcp_test_server.py`](../../surfsense_local/backend/tests/mcp_test_server.py)) through the routes: each refusal, a key that reaches the server and never comes back out, the switches, disconnecting and the third-party switch. [`tests/integration/plugins/gateway/`](../../surfsense_local/backend/tests/integration/plugins/gateway/) holds readiness and tools added later, and [`tests/unit/plugins/`](../../surfsense_local/backend/tests/unit/plugins/) the MCP client, the approval rules and URL spelling. The agent's side is in [agent](agent.md#tests).
- **Frontend:** [`plugins-settings.test.tsx`](../../surfsense_local/frontend/src/features/plugins/plugins-settings.test.tsx) drives the screen against a stand-in API: listing, adding with a key, a refusal, the tool and plugin switches, approval, disconnecting and the third-party consent.

## Known gaps

- Only servers added by URL: SurfSense's own plugins and the third-party registry are not listed yet ([proposal](../proposals/plugins/core/02-registry.md)).
- Only remote MCP servers, reached over HTTP. A local server started by a command, such as `npx` or `uvx`, cannot be added; whether it should be is an [open question](../proposals/plugins/README.md#open-questions).
- A key can be given only when connecting, and OAuth sign-in does not exist; a server that needs it cannot be connected ([proposal](../proposals/plugins/remote/01-mcp-client.md)).
- The screen shows no status: a server that went down or refused its key is seen only when an agent turn names it.
- A tool switched off because it changed says nothing more on the screen than any other switch that is off.
- Plugins reach Agentic threads only; Basic threads get none until the chat engine's router step ([proposal](../proposals/plugins/core/03-engines.md#the-chat-engine-later)).
