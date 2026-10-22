# Plugins

Plugins keep reaching opencode through SurfSense's gateway, one URL per plugin per thread with a key that opens nothing else ([ADR 0064](../../adr/0064-agent-runtimes-reach-plugins-through-surfsenses-gateway.md)). The gateway's code ran unchanged against 2.x for these measurements, with only its database calls stood in.

## Registration

`PUT /api/experimental/mcp/:name` with the thread's folder and `{config: {type: "remote", url, headers, oauth: false, codemode: false, timeout: {startup, catalog, execution}}}` ([`registration.py`](../../../surfsense_local/backend/modules/agent/tool_endpoint/registration.py), [`give_plugins.py`](../../../surfsense_local/backend/modules/agent/plugin_tools/give_plugins.py)). It answers 204 whether or not the server connected, so the backend reads `GET /api/mcp` for `connected`, and waits for it before the first prompt: a prompt sent within about 120 ms of the `PUT` starts without the server's tools. A `PUT` without the folder silently registers into the server's own working folder.

The route is experimental upstream, and used on purpose. It keeps one URL and one key per thread, a key that opens that thread's tools and nothing else ([ADR 0064](../../adr/0064-agent-runtimes-reach-plugins-through-surfsenses-gateway.md)), and touches only the thread being prepared, as 1.x's runtime route does today. The stable way, servers declared under `mcp.servers` in the configuration file, would give every thread the same URL, leave telling threads apart to the session id opencode sends, which its docs say not to rely on for security, and rewrite a file every thread reads at each connect. The version is pinned, an integration test fails if a new release changes the route, and the configuration file is the way out if one removes it.

2.x's MCP client sends protocol `2025-11-25`, `_meta {"ai.opencode/sessionID", progressToken}` on each `tools/call`, and accepts the gateway's 405 to `GET`.

## SSE

2.x's client speaks Streamable HTTP only. Against an SSE-only server it posts `initialize`, gets 405 and marks the server failed; it never sends the `GET` that [`sse_endpoint.py`](../../../surfsense_local/backend/modules/agent/plugin_gateway/sse_endpoint.py) rewrites. The same gateway works on 1.18.34.

SSE-only plugins are no longer supported, in one release with the opencode change:

- The registry drops `transport: sse` from an entry and its live check fails an SSE-only server ([`entry_rules.py`](../../../plugins/registry/check/registry_check/static/entry_rules.py), [registry README](../../../plugins/registry/README.md), which already says SurfSense does not speak SSE).
- Connecting a server stops falling back to SSE and refuses one that answers only there, with its own reason ([`either_transport.py`](../../../surfsense_local/backend/modules/plugins/remote/either_transport.py)). [`transport_moved.py`](../../../surfsense_local/backend/modules/plugins/remote/transport_moved.py) moves a server only from SSE to Streamable HTTP.
- A plugin installed with `transport: sse` shows that it uses the older transport and how to reconnect it on its Streamable HTTP address, rather than "Couldn't reach" on every turn.
- The Claude plan engine refuses them too: Claude Code still speaks SSE, and a thread moves between engines when its model changes.

## Stopping a call

Interrupting a turn, or a call's `timeout.execution` passing, sends `notifications/cancelled {requestId, reason}`; the gateway forwards it upstream. The cancelled request's stream stays open and the upstream call runs on. A timed-out call fails as `MCP tool "x" on server "y" failed: Request timed out`; 1.x's `MCP error -32001` is gone, so [`stop_plugin_calls.py`](../../../surfsense_local/backend/modules/agent/plugin_tools/stop_plugin_calls.py) stops matching it and the gateway turns the cancel into the plugin host's own stop for that thread instead.

Progress notifications are dropped ([`core/src/mcp/client.ts`](https://github.com/anomalyco/opencode/blob/v2.1.2/packages/core/src/mcp/client.ts) registers an empty handler) and do not extend `timeout.execution`, so the 200 s and 300 s limits become hard caps.

## Results

| Result | Stored | The model sees |
|---|---|---|
| text, or `structuredContent` with text | the text | the text |
| `structuredContent` only | the JSON as text | the JSON |
| `isError` | `error {type: "tool.execution", message}` | the error |
| an image | a file item | for a model without image input, a text saying it cannot read it |
| over 50 KB or 2,000 lines | cut, with `metadata.outputPath` naming the whole in `tool-output/` | the cut text and where the rest is |

[`saved_results.py`](../../../surfsense_local/backend/modules/agent/plugin_tools/saved_results.py) reads `state.content`; there is no `state.output`.

## Names

A tool is `<server>_<tool>`, each part with characters outside `[A-Za-z0-9_-]` replaced by `_`, as 1.x. 2.x does not shorten names, so SurfSense keeps them at 64 characters ([`qualified_name.py`](../../../surfsense_local/backend/modules/plugins/gateway/qualified_name.py), whose comment about a `plugins_` prefix describes neither line). Two servers whose names clean to the same text collide and only one's tools are offered, so a plugin's server name stays unique after cleaning.

## Tools added later

2.x re-lists a server when it sends `tools/list_changed`, within a call's streamed answer or on its own `GET` stream. The gateway answers `GET` with 405, so a plugin's change outside a call reaches opencode at the next connect. [`changed_tools.py`](../../../surfsense_local/backend/modules/agent/plugin_tools/changed_tools.py) keeps listing in the background as today.

## Example requests

A registry entry can list, per tool, a few requests a user might make that the tool answers. SurfSense indexes them beside the tool's name and description, so the opencode agent's retrieval finds the tool from the words users use. They were the largest single gain measured, 10 to 17 points of tasks fully covered ([tool calls](04-tool-calls.md#retrieval-measured)). The field is optional, and the registry's static check only bounds its size; a custom plugin and an entry without it are indexed from their tools alone. SurfSense writes them for its own plugins.

## Asking the user

2.x tells servers it accepts elicitation, and turns a server's request for input into a form it waits on. SurfSense shows no such form, so the call would hang until its timeout; elicitation is refused.
