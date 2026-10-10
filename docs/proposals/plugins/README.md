---
status: proposed
code:
  - plugins/registry/
  - plugins/proprietary/
  - plugins/bundles/core/
  - surfsense_local/backend/modules/plugins/
  - surfsense_local/backend/modules/agent/plugin_tools/
  - surfsense_local/backend/modules/chat/plugin_router/
  - surfsense_local/frontend/src/features/plugins/
---

# Plugins

> A plugin is an MCP server that gives SurfSense's models tools. Every caller, opencode, the chat engine and the user's `@` mentions, reaches it through one Tool Gateway, and results come back into the turn. Remote plugins, hosted by their publishers, come first; plugins on the user's machine come later, as [bundles](bundles/README.md).

This replaces the earlier design, where a plugin was a sidebar action with a form whose output went into Sources and reached the models only through search. That design is kept in [`bundles/`](bundles/README.md), where its local-runtime parts wait for bundles ([ADR 0051](../../adr/0051-plugins-are-mcp-servers-behind-one-tool-gateway.md)).

## Files

```
plugins/
  README.md     this page: what plugins are, the locked decisions, the order of work
  core/         what every kind of plugin shares
  remote/       plugins hosted by their publishers, built first
  bundles/      plugins that run on the user's machine, deferred
```

**[`core/`](core/01-architecture.md)**: the same for every kind of plugin.

| File | Covers |
|---|---|
| [`01-architecture.md`](core/01-architecture.md) | The Tool Gateway, tool sources, naming, the tables, the routes |
| [`02-registry.md`](core/02-registry.md) | The registry, the one list of plugins, who publishes, review, Restricted mode, tools added later, delisting, how the app gets the list |
| [`03-engines.md`](core/03-engines.md) | opencode, the chat engine's router step, `@` mentions, results, Save to Sources |
| [`04-trust.md`](core/04-trust.md) | Approval, permissions, what a plugin can and cannot do, prompt injection |
| [`05-paid.md`](core/05-paid.md) | SurfSense's paid plugins on the license key, checked on the server, and third parties billing on their own |
| [`06-later.md`](core/06-later.md) | What comes after, and the extension points that keep it additive |

**[`remote/`](remote/README.md)**: the first kind of plugin.

| File | Covers |
|---|---|
| [`README.md`](remote/README.md) | What a remote plugin is, how one works, who hosts what |
| [`01-mcp-client.md`](remote/01-mcp-client.md) | The app's MCP client, signing in, credentials, egress |
| [`02-surfsense-servers.md`](remote/02-surfsense-servers.md) | The servers SurfSense hosts, and SurfSense Scrapers as its own container |

**[`bundles/`](bundles/README.md)**: deferred. Plugins that run on the user's machine, and the earlier design they build on.

## What it looks like

- **A user** opens Settings → Plugins, sees every plugin; other publishers' are greyed until Restricted mode is turned off. They press **Connect**, sign in or paste a key, allow the plugin's host, and its tools are ready.
- **In an agent thread**, opencode sees the plugin's tools beside SurfSense's own and calls one when it needs it.
- **In a chat thread**, the model never calls a tool. When a question fits a plugin, SurfSense asks the model, under a JSON schema, which tool and with what inputs, calls it, and the model answers with the result.
- **Anywhere**, the user can type `@notion search Q3 plan` to call a tool directly.
- **A result** shows as a step in the thread. "Save to Sources" keeps it as a note.

## Prior art

| Product | What it does | What this design takes |
|---|---|---|
| [Pi](https://github.com/earendil-works/pi) | Its own tool pipeline, with MCP as a built-in extension adapting servers into it through Pi's own client; exposure modes and a tool search; MCP annotations driving permission checks; results trimmed at 20 KB | The structure: one gateway of SurfSense's own, MCP as a source behind it, a small client of our own, exposure, annotations, trimming. Not its in-process extensions, its installs from npm and git, or its lack of review |
| Claude's connectors | A reviewed directory of remote MCP servers, custom connectors by URL, local servers packaged as [MCP Bundles](https://github.com/modelcontextprotocol/mcpb) | Remote plugins listed and reviewed; custom plugins by URL; MCPB as the format of later bundles |
| [Obsidian](https://github.com/obsidianmd/obsidian-releases) | One list of community plugins on its own server, each pointing at the author's repository and its GitHub releases; every version scanned; community plugins off until turned on | One list served from SurfSense's host; code and files staying with their authors; Restricted mode; scanning every bundle version |

## Locked decisions

| Decision | Choice |
|---|---|
| Protocol | MCP, unmodified, protocol `2025-11-25`. No protocol of SurfSense's own: its controls sit around MCP, in the registry and the app. A plugin server sees only standard MCP and ordinary HTTP sign-in headers, so any MCP server works as a plugin unchanged, and SurfSense's own servers work in any MCP client |
| The core | One Tool Gateway in the API: the only way any caller reaches any plugin tool. Policy, approval, logging and trimming live there once |
| Sources of tools | Remote MCP servers over HTTPS first. Bundles (`kind: bundle`) later, through the same gateway |
| Who hosts a remote plugin | Its publisher: SurfSense, a company, or a community developer |
| Name | "Plugins", in the app and in the docs |
| The registry | One file, `plugins/registry/plugins.json` in this repository, listing every plugin, SurfSense's included, added to by pull request and reviewed once per entry. Signed and served from SurfSense's plugin host, so it grows without app updates ([`core/02-registry.md`](core/02-registry.md)). "The registry" always means this file |
| Where a plugin's code lives | With its publisher: a remote server on its host, a bundle in its author's repository and releases. The list only points at it |
| Publishers | `surfsense`, `partner` (a verified company) or `community`, set in the registry, never by the plugin |
| Restricted mode | Every plugin not published by SurfSense is off until the user turns third-party plugins on once ([ADR 0053](../../adr/0053-plugins-are-listed-in-a-registry-and-third-party-ones-start-off.md)) |
| Custom plugins | A user can add any remote MCP server by URL, labelled "Not reviewed by SurfSense", behind Restricted mode |
| Tools added later | A tool a server adds after the user connected starts off; the app asks before turning it on |
| opencode | Plugin tools reach it as a second MCP server, `plugins`, registered before each turn beside `surfsense` |
| Chat engine | The model never calls tools. A router step chooses a tool under a JSON schema, then fills its inputs under the tool's own schema, and SurfSense makes the call ([ADR 0052](../../adr/0052-the-chat-model-never-calls-tools.md)) |
| `@` mentions | The user names the tool; the model only fills its inputs |
| Results | Belong to the turn and are stored with the call. Nothing reaches Sources unless the user saves it |
| Approval | From the tool's MCP annotations, in SurfSense's own dialog, for every caller |
| Egress | A plugin's hosts need consent before it connects, and appear in Settings → Network with its name |
| Paid | SurfSense's paid plugins are unlocked by the SurfSense license key, which reaches only SurfSense's servers and is checked there on every call, never in the app. A third party bills on its own side and never sees the key ([`core/05-paid.md`](core/05-paid.md)) |
| SurfSense's own plugin servers | In [`plugins/`](../../../plugins/README.md) (Apache-2.0) and `plugins/proprietary/` (Business Source License 1.1), each its own container ([ADR 0047](../../adr/0047-premium-plugins-are-source-available.md), [`remote/02-surfsense-servers.md`](remote/02-surfsense-servers.md)) |
| `surfsense_mcp` | Stays the MCP server for outside clients. The app does not use it; SurfSense's plugins are their own servers |
| Offline | The app works with no plugin. Plugins are the one optional layer that connects out, and the interface says so: "SurfSense works offline. Plugins are optional and connect to the services you choose." Organisation policy can turn them off ([`core/04-trust.md`](core/04-trust.md#organisation-policy)) |

## Workstreams

| Stream | Owns | Needs |
|---|---|---|
| **Registry** | `plugins/registry/plugins.json`, its schema and CI check, signing and publishing it to SurfSense's plugin host, the copy the app ships and refreshes | a host for the signed file |
| **MCP client** | `modules/plugins/mcp_client/`: Streamable HTTP, sign-in, credentials | nothing |
| **Gateway** | `modules/plugins/gateway/`, the tables, approval, permissions, results | the MCP client |
| **Screen** | `frontend/src/features/plugins/`: Settings → Plugins, Connect, Restricted mode, permissions, activity | the gateway's routes; can start against their shapes |
| **opencode** | `modules/agent/plugin_tools/` | the gateway |
| **Chat router** | `modules/chat/plugin_router/`, `@` mentions, the chat eval's router test | the gateway |
| **SurfSense scrapers** | `plugins/proprietary/surfsense-scrapers/`: the scraping code copied out of `surfsense_backend`, the MCP server, the license check, the container with Redis and SearXNG, its deployment | the root `LICENSE` line for `plugins/proprietary/` |
| **Contributor guide** | [`plugins/README.md`](../../../plugins/README.md), rewritten: building a remote MCP server, trying it with a custom plugin by URL, the registry pull request | the registry's rules |
| **Bundles** | [`bundles/`](bundles/README.md) | deferred |

**Demo:** a thread on a tool-calling model connects a test remote server added as a custom plugin by URL, the agent calls one of its tools, and the result shows as a step. The same question in a chat thread with the router on gets the same tool called and answered from.

**Ship:** Settings → Plugins lists the registry, a user connects SurfSense Scrapers with a trial license and a partner plugin with OAuth, both engines and `@` mentions use them, and Restricted mode, approval and Save to Sources work.

## Order of work

1. **License mode on the scraper API** ([contract 2](../../contracts/02-scraper-api-auth.md)), in `surfsense_backend`, for outside clients such as `surfsense_mcp`, whose personal keys are purged on 18 Oct 2026. It starts at once and in parallel; the plugins do not depend on it.
2. **MCP client, gateway, tables and the opencode endpoint**, shown with a test server added as a custom plugin by URL. The agent calling a plugin is the first thing to demonstrate.
3. **Settings → Plugins**: Connect, sign-in, egress consent, Restricted mode, tool switches, approval, activity.
4. **The registry**: `plugins.json`, its check, signing and publishing to SurfSense's host, the app's refresh.
5. **The chat router and `@` mentions**, with the chat eval's router test.
6. **SurfSense Scrapers**, its own container ([`remote/02-surfsense-servers.md`](remote/02-surfsense-servers.md)). Then partners' entries.
7. **Bundles**, when something needs them.

## What this design gives up

Against the earlier design, where plugins ran locally from reviewed code:

- **Offline use of plugins.** A remote plugin needs the network. The app itself still works offline, and bundles bring offline plugins back later.
- **Data staying on the machine.** Each call's arguments go to the plugin's publisher. Consent per host, the privacy policy shown before Connect, and approval with the exact arguments make that visible.
- **Seeing the code.** SurfSense reviews a listing, not the server behind it, which can change at any time. Tools added or changed later start off, and a plugin can be delisted.
- **Availability.** A plugin stops working if its publisher's server does.
- **One extra step for chat.** The router costs one or two model calls when tools are ready, and how well small models choose is unmeasured.

In return, both engines call plugins and get live results, existing MCP servers become plugins with one pull request, publishers update without app releases, and there is far less for SurfSense to build before the first plugin ships.

## What happens to the code already built

The local runner, the SDK, the CLI and the manifest rules in [`plugins/bundles/core/`](../../../plugins/bundles/core/) and [`modules/plugins/`](../../../surfsense_local/backend/modules/plugins/) were built for the earlier design. They stay in the tree, unwired, as the base for bundles: the runner becomes the bundle host, the SDK's `@action` becomes `@tool`. `document_metadata` on notes and the `api-url` file stay in use. [`bundles/README.md`](bundles/README.md) lists what changes when bundles are picked up. [`plugins/README.md`](../../../plugins/README.md), the contributor guide, still describes the earlier design and is rewritten by the contributor guide stream.

## Out of scope

Plugins that change SurfSense itself (providers, interface, prompts); local MCP servers started by an arbitrary command such as `npx` or `uvx`; a sandbox; payments for third parties; plugin-authored interface.

## Open questions

- The citation a chat answer gives a tool result, beside today's chunk citations.
- How long tool results are kept and how large a stored one may be.
- The router's default per model, from the chat eval's router test.
- Where SurfSense's plugin servers and the signed list are deployed, and under which hostname.
- Whether outside clients, `surfsense_mcp` and direct users of the scraper API, move to the scrapers container once the backend's scraper API is retired.
