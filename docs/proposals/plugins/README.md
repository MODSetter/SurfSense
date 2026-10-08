---
status: proposed
code:
  - plugins/registry/
  - plugins/proprietary/
  - plugins/core/
  - surfsense_local/backend/modules/plugins/
  - surfsense_local/backend/modules/agent/plugin_tools/
  - surfsense_local/backend/modules/chat/plugin_router/
  - surfsense_local/frontend/src/features/plugins/
---

# Plugins

> A plugin gives SurfSense's models tools from outside the app. Every plugin is an MCP server. The app reaches all of them through one Tool Gateway, and opencode, the chat engine and the user call their tools from a thread; a result comes back into the turn. The first plugins are remote: the publisher hosts the server, and the user connects to it from Settings. Plugins running on the user's machine come later, as [bundles](bundles/README.md).

This replaces the earlier design, where a plugin was a sidebar action with a form whose output went into Sources and reached the models only through search. That design is kept in [`bundles/`](bundles/README.md), where its local-runtime parts wait for bundles ([ADR 0051](../../adr/0051-plugins-are-mcp-servers-behind-one-tool-gateway.md)).

## Files

| File | Covers |
|---|---|
| [`01-architecture.md`](01-architecture.md) | The Tool Gateway, tool sources, naming, the tables |
| [`02-registry.md`](02-registry.md) | The list of plugins, who publishes, review, Restricted mode, tools added later, delisting |
| [`03-remote-plugins.md`](03-remote-plugins.md) | The MCP client, sign-in, credentials, egress, SurfSense's own servers |
| [`04-engines.md`](04-engines.md) | opencode, the chat engine's router step, `@` mentions, results, Save to Sources |
| [`05-trust.md`](05-trust.md) | Approval, permissions, what a remote plugin can and cannot do, prompt injection |
| [`06-paid.md`](06-paid.md) | SurfSense's paid plugins on the license key, and third parties billing on their own |
| [`07-later.md`](07-later.md) | What comes after, and the extension points that keep it additive |
| [`bundles/`](bundles/README.md) | Deferred: plugins that run on the user's machine |

## What it looks like

- **A user** opens Settings → Plugins, sees SurfSense's plugins, free and paid, and, once Restricted mode is off, other publishers' plugins. They press **Connect**, sign in or paste a key, allow the plugin's host, and its tools are ready.
- **In an agent thread**, opencode sees the plugin's tools beside SurfSense's own and calls one when it needs it.
- **In a chat thread**, the model never calls a tool. When a question fits a plugin, SurfSense asks the model, under a JSON schema, which tool and with what inputs, calls it, and the model answers with the result.
- **Anywhere**, the user can type `@notion search Q3 plan` to call a tool directly.
- **A result** shows as a step in the thread. "Save to Sources" keeps it as a note.

## Locked decisions

| Decision | Choice |
|---|---|
| Protocol | MCP, unmodified, protocol `2025-11-25`. No protocol of SurfSense's own |
| The core | One Tool Gateway in the API: the only way any caller reaches any plugin tool. Policy, approval, logging and trimming live there once |
| Sources of tools | Remote MCP servers over HTTPS first. Bundles (`kind: bundle`) later, through the same gateway |
| Who hosts a remote plugin | Its publisher: SurfSense, a company, or a community developer |
| Name | "Plugins", in the app and in the docs |
| The list | `plugins/registry/connectors.json` in this repository, added to by pull request, reviewed once per entry |
| Publishers | `surfsense`, `partner` (a verified company) or `community`, set by the registry, never by the plugin |
| Restricted mode | Every plugin not published by SurfSense is off until the user turns third-party plugins on once ([ADR 0053](../../adr/0053-plugins-are-listed-in-a-registry-and-third-party-ones-start-off.md)) |
| Custom plugins | A user can add any remote MCP server by URL, labelled "Not reviewed by SurfSense", behind Restricted mode |
| Tools added later | A tool a server adds after the user connected starts off; the app asks before turning it on |
| opencode | Plugin tools reach it as a second MCP server, `plugins`, registered before each turn beside `surfsense` |
| Chat engine | The model never calls tools. A router step chooses a tool under a JSON schema, then fills its inputs under the tool's own schema, and SurfSense makes the call ([ADR 0052](../../adr/0052-the-chat-model-never-calls-tools.md)) |
| `@` mentions | The user names the tool; the model only fills its inputs |
| Results | Belong to the turn and are stored with the call. Nothing reaches Sources unless the user saves it |
| Approval | From the tool's MCP annotations, in SurfSense's own dialog, for every caller |
| Egress | A plugin's hosts need consent before it connects, and appear in Settings → Network with its name |
| Paid | SurfSense's paid plugins are unlocked by the SurfSense license key, which reaches only SurfSense's servers. A third party bills on its own side and never sees the key ([`06-paid.md`](06-paid.md)) |
| SurfSense's own plugin servers | In [`plugins/`](../../../plugins/README.md): free ones under Apache-2.0, paid ones in `plugins/proprietary/` under the Business Source License 1.1 ([ADR 0047](../../adr/0047-premium-plugins-are-source-available.md)). SurfSense hosts them all |
| `surfsense_mcp` | Stays the MCP server for outside clients. The app does not use it; SurfSense's plugins are their own servers |
| Offline | The app works with no plugin. Plugins are the one optional layer that connects out |

## Workstreams

| Stream | Owns | Needs |
|---|---|---|
| **Registry** | `plugins/registry/`, its schema and CI check, the catalog the app ships and refreshes | nothing |
| **MCP client** | `modules/plugins/mcp_client/`: Streamable HTTP, sign-in, credentials | nothing |
| **Gateway** | `modules/plugins/gateway/`, the tables, approval, permissions, results | the MCP client |
| **Screen** | `frontend/src/features/plugins/`: Settings → Plugins, Connect, Restricted mode, permissions, activity | the gateway's routes; can start against their shapes |
| **opencode** | `modules/agent/plugin_tools/` | the gateway |
| **Chat router** | `modules/chat/plugin_router/`, `@` mentions, the chat eval's router test | the gateway |
| **SurfSense scrapers** | `plugins/proprietary/surfsense-scrapers/`, its hosting | license mode on the scraper API ([contract 2](../../contracts/02-scraper-api-auth.md)) |
| **Bundles** | [`bundles/`](bundles/README.md) | deferred |

**Demo:** a thread on a tool-calling model connects a test remote server from the registry, the agent calls one of its tools, and the result shows as a step. The same question in a chat thread with the router on gets the same tool called and answered from.

**Ship:** Settings → Plugins lists the registry, a user connects SurfSense Scrapers with a trial license and a partner plugin with OAuth, both engines and `@` mentions use them, and Restricted mode, approval and Save to Sources work.

## What happens to the code already built

The local runner, the SDK, the CLI and the manifest rules in [`plugins/core/`](../../../plugins/core/) and [`modules/plugins/`](../../../surfsense_local/backend/modules/plugins/) were built for the earlier design. They stay in the tree, unwired, as the base for bundles: the runner becomes the bundle host, the SDK's `@action` becomes `@tool`. `document_metadata` on notes and the `api-url` file stay in use. [`bundles/README.md`](bundles/README.md) lists what changes when bundles are picked up.

## Out of scope

Plugins that change SurfSense itself (providers, interface, prompts); local MCP servers started by an arbitrary command such as `npx` or `uvx`; a sandbox; payments for third parties; plugin-authored interface.

## Open questions

- The citation a chat answer gives a tool result, beside today's chunk citations.
- How long tool results are kept and how large a stored one may be.
- The router's default per model, from the chat eval's router test.
- Where SurfSense's plugin servers are deployed, and under which hostname.
- How SurfSense's scrapers server learns the scraper API workspace for a license, since contract 2 creates one per license on first call.
- Whether the root [`LICENSE`](../../../LICENSE) names `plugins/proprietary/`; a maintainer has to approve that line ([`06-paid.md`](06-paid.md)).
