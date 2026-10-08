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

## Prior art

| Product | What it does | What this design takes |
|---|---|---|
| [Pi](https://github.com/earendil-works/pi) | Its own tool pipeline, with MCP as a built-in extension adapting servers into it through Pi's own client; exposure modes and a tool search; MCP annotations driving permission checks; results trimmed at 20 KB | The structure: one gateway of SurfSense's own, MCP as a source behind it, a small client of our own, exposure, annotations, trimming. Not its in-process extensions, its installs from npm and git, or its lack of review |
| Claude's connectors | A reviewed directory of remote MCP servers, custom connectors by URL, local servers packaged as [MCP Bundles](https://github.com/modelcontextprotocol/mcpb) | Remote plugins listed and reviewed; custom plugins by URL; MCPB as the format of later bundles |
| [Obsidian](https://github.com/obsidianmd/obsidian-releases) | One list of community plugins on its own server, each pointing at the author's repository and its GitHub releases; every version scanned; community plugins off until turned on | One list served from SurfSense's host; code and files staying with their authors; Restricted mode; scanning every bundle version |

## Locked decisions

| Decision | Choice |
|---|---|
| Protocol | MCP, unmodified, protocol `2025-11-25`. No protocol of SurfSense's own |
| The core | One Tool Gateway in the API: the only way any caller reaches any plugin tool. Policy, approval, logging and trimming live there once |
| Sources of tools | Remote MCP servers over HTTPS first. Bundles (`kind: bundle`) later, through the same gateway |
| Who hosts a remote plugin | Its publisher: SurfSense, a company, or a community developer |
| Name | "Plugins", in the app and in the docs |
| The list | One file, `plugins/registry/plugins.json` in this repository, listing every plugin, SurfSense's included, added to by pull request and reviewed once per entry. Signed and served from SurfSense's own host, so it grows without app updates ([`02-registry.md`](02-registry.md)) |
| Where a plugin's code lives | With its publisher: a remote server on its host, a bundle in its author's repository and releases. The list only points at it |
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
| Paid | SurfSense's paid plugins are unlocked by the SurfSense license key, which reaches only SurfSense's servers and is checked there on every call, never in the app. A third party bills on its own side and never sees the key ([`06-paid.md`](06-paid.md)) |
| SurfSense's own plugin servers | In [`plugins/`](../../../plugins/README.md): free ones under Apache-2.0, paid ones in `plugins/proprietary/`, where everything, helpers included, is under the Business Source License 1.1 ([ADR 0047](../../adr/0047-premium-plugins-are-source-available.md)). Each runs as its own container that SurfSense deploys, sharing no code or service with `surfsense_backend`. SurfSense Scrapers carries the scraping code itself, moved out of the backend |
| `surfsense_mcp` | Stays the MCP server for outside clients. The app does not use it; SurfSense's plugins are their own servers |
| Offline | The app works with no plugin. Plugins are the one optional layer that connects out, and the interface says so: "SurfSense works offline. Plugins are optional and connect to the services you choose." Organisation policy can turn them off ([`05-trust.md`](05-trust.md#organisation-policy)) |

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

**Demo:** a thread on a tool-calling model connects a test remote server from the registry, the agent calls one of its tools, and the result shows as a step. The same question in a chat thread with the router on gets the same tool called and answered from.

**Ship:** Settings → Plugins lists the registry, a user connects SurfSense Scrapers with a trial license and a partner plugin with OAuth, both engines and `@` mentions use them, and Restricted mode, approval and Save to Sources work.

## Order of work

1. **License mode on the scraper API** ([contract 2](../../contracts/02-scraper-api-auth.md)), in `surfsense_backend`, for outside clients such as `surfsense_mcp`, whose personal keys are purged on 18 Oct 2026. It starts at once and in parallel; the plugins do not depend on it.
2. **MCP client, gateway, tables and the opencode endpoint**, shown with a test server listed in the registry. The agent calling a plugin is the first thing to demonstrate.
3. **Settings → Plugins**: Connect, sign-in, egress consent, Restricted mode, tool switches, approval, activity.
4. **The registry**: `plugins.json`, its check, signing and publishing to SurfSense's host, the app's refresh.
5. **The chat router and `@` mentions**, with the chat eval's router test.
6. **SurfSense Scrapers**: copy the scraping code into its own container, add the MCP server and the license check, deploy it. The backend's copy is deleted once outside clients no longer use the backend's scraper API, never before the purge. Then partners' entries.
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

The local runner, the SDK, the CLI and the manifest rules in [`plugins/core/`](../../../plugins/core/) and [`modules/plugins/`](../../../surfsense_local/backend/modules/plugins/) were built for the earlier design. They stay in the tree, unwired, as the base for bundles: the runner becomes the bundle host, the SDK's `@action` becomes `@tool`. `document_metadata` on notes and the `api-url` file stay in use. [`bundles/README.md`](bundles/README.md) lists what changes when bundles are picked up. [`plugins/README.md`](../../../plugins/README.md), the contributor guide, still describes the earlier design and is rewritten by the contributor guide stream.

## Out of scope

Plugins that change SurfSense itself (providers, interface, prompts); local MCP servers started by an arbitrary command such as `npx` or `uvx`; a sandbox; payments for third parties; plugin-authored interface.

## Open questions

- The citation a chat answer gives a tool result, beside today's chunk citations.
- How long tool results are kept and how large a stored one may be.
- The router's default per model, from the chat eval's router test.
- Where SurfSense's plugin servers and the signed list are deployed, and under which hostname.
- Whether outside clients, `surfsense_mcp` and direct users of the scraper API, move to the scrapers container once the backend's scraper API is retired.
- Whether the root [`LICENSE`](../../../LICENSE) names `plugins/proprietary/`; a maintainer has to approve that line ([`06-paid.md`](06-paid.md)).
