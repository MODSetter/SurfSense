---
status: proposed
code:
  - plugins/registry/
  - plugins/remote/
  - surfsense_local/backend/modules/plugins/lists/
  - plugins/bundles/core/
  - surfsense_local/backend/modules/plugins/
  - surfsense_local/backend/modules/agent/plugin_tools/
  - surfsense_local/frontend/src/features/plugins/
---

# Plugins

> A plugin is an MCP server that gives SurfSense's models tools. SurfSense decides which tools each caller gets and which must be approved: the agent's opencode calls the plugin servers it is given each turn directly, the chat engine will reach them through one Tool Gateway, and results come back into the turn. Remote plugins, hosted by their publishers, come first; plugins on the user's machine come later, as [bundles](bundles/README.md).

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
| [`02-registry.md`](core/02-registry.md) | The two plugin lists, first-party and registry, who publishes, review, allowing third-party plugins, tools added later, delisting, how the app gets each list |
| [`03-engines.md`](core/03-engines.md) | opencode, `@` mentions, results, Save to Sources; the chat engine's router step, later |
| [`04-trust.md`](core/04-trust.md) | Approval, permissions, what a plugin can and cannot do, prompt injection |
| [`05-paid.md`](core/05-paid.md) | SurfSense's paid plugins on the license key, checked on the server, and third parties billing on their own |
| [`06-later.md`](core/06-later.md) | What comes after, and the extension points that keep it additive |

**[`remote/`](remote/README.md)**: the first kind of plugin.

| File | Covers |
|---|---|
| [`README.md`](remote/README.md) | What a remote plugin is, how one works, who hosts what |
| [`01-mcp-client.md`](remote/01-mcp-client.md) | The app's MCP client, signing in, credentials, egress |
| [`02-surfsense-servers.md`](remote/02-surfsense-servers.md) | The plugin host that runs SurfSense's plugins and serves the registry, the code layout, SurfSense Scrapers |

**[`bundles/`](bundles/README.md)**: deferred. Plugins that run on the user's machine, and the earlier design they build on.

## What it looks like

- **A user** opens Settings → Plugins and sees first-party plugins, SurfSense's own, at once, with no network; third-party plugins appear once they allow them. They press **Connect**, sign in or paste a key, allow the plugin's host, and its tools are ready.
- **In an agent thread**, opencode sees the plugin's tools beside SurfSense's own and calls one when it needs it.
- **In an agent thread**, the user can also type `@notion search` to ask for a tool by name; the agent fills its inputs.
- **In a chat thread**, plugins come later. Settings → Plugins says plugins work in Agentic threads.
- **A result** shows as a step in the thread. "Save to Sources" keeps it as a note.

## Prior art

| Product | What it does | What this design takes |
|---|---|---|
| [Pi](https://github.com/earendil-works/pi) | Its own tool pipeline, with MCP as a built-in extension adapting servers into it through Pi's own client; exposure modes and a tool search; MCP annotations driving permission checks; results trimmed at 20 KB | The structure: one gateway of SurfSense's own, MCP as a source behind it, exposure, annotations, trimming. Not its in-process extensions, its installs from npm and git, or its lack of review |
| Claude's connectors | A reviewed directory of remote MCP servers, custom connectors by URL, local servers packaged as [MCP Bundles](https://github.com/modelcontextprotocol/mcpb) | Remote plugins listed and reviewed; custom plugins by URL; MCPB as the format of later bundles |
| [Obsidian](https://github.com/obsidianmd/obsidian-releases) | One list of community plugins on its own server, each pointing at the author's repository and its GitHub releases; every version scanned; community plugins off until turned on | One list served from SurfSense's host; code and files staying with their authors; third-party plugins off until allowed; scanning every bundle version |

## Locked decisions

| Decision | Choice |
|---|---|
| Protocol | MCP, unmodified, protocol `2025-11-25`. No protocol of SurfSense's own: its controls sit around MCP, in the plugin lists and the app. A plugin server sees only standard MCP and ordinary HTTP sign-in headers, so any MCP server works as a plugin unchanged, and SurfSense's own servers work in any MCP client |
| The core | SurfSense decides, in one place, which plugin tools each caller gets and which must be approved. The agent's opencode calls plugin servers itself under the rules SurfSense gives each turn, so SurfSense is in no call's path; SurfSense's own callers go through one Tool Gateway |
| Sources of tools | Remote MCP servers over HTTPS first. Bundles (`kind: bundle`) later, through the same gateway |
| Who hosts a remote plugin | Its publisher: SurfSense, a company, or a community developer |
| Name | "Plugins", in the app and in the docs |
| The lists | SurfSense's plugins are in a first-party list packaged into the app, shown with no network or consent. Every third-party plugin is in one file, `plugins/registry/plugins.json` in this repository, added to by pull request and reviewed once per entry, signed and served from SurfSense's plugin host, and fetched once the user allows third-party plugins, so it grows without app updates ([`core/02-registry.md`](core/02-registry.md)). "The registry" always means this file. No list holds plugin code |
| Where a plugin's code lives | With its publisher: a remote server on its host, a bundle in its author's repository and releases. The list only points at it |
| Publishers | `surfsense`, `partner` (a verified company) or `community`, set by the list, never by the plugin. Only the first-party list says `surfsense` |
| Third-party plugins | Every plugin not published by SurfSense is off until the user allows third-party plugins once, which is also when the app fetches the registry. The switch plays the part of Obsidian's Restricted mode, named for what it does ([ADR 0053](../../adr/0053-plugins-are-listed-in-a-registry-and-third-party-ones-start-off.md)) |
| Custom plugins | A user can add any remote MCP server by URL, labelled "Not reviewed by SurfSense", off until third-party plugins are allowed |
| Tools added later | A tool a server adds after the user connected starts off; the app asks before turning it on |
| opencode | Calls plugin servers itself, through its own MCP client: before each turn SurfSense gives it each ready plugin's server, with its sign-in as headers, and an `allow`, `ask` or `deny` rule per tool, every unreviewed tool denied ([`core/03-engines.md`](core/03-engines.md#opencode)) |
| Chat engine | Plugins reach agent threads first. The chat engine gets them later, through a router step: its model never calls tools; it chooses a tool and fills its inputs under JSON schemas, and SurfSense makes the call ([ADR 0052](../../adr/0052-the-chat-model-never-calls-tools.md), [`core/03-engines.md`](core/03-engines.md#the-chat-engine-later)) |
| `@` mentions | In agent threads: the user names a plugin, the agent picks its tools and fills their inputs, and approval is as for any call |
| Results | Belong to the turn: the agent's are kept in its opencode session, and SurfSense keeps no copy. Nothing reaches Sources unless the user saves it |
| Approval | Decided by the gateway from the tool's MCP annotations and the user's setting for it; in agent threads opencode's own request, asked on its step in the reply, Allow once or Deny ([`core/04-trust.md`](core/04-trust.md#approval)) |
| Egress | A plugin's hosts need consent before it connects, and appear in Settings → Network with its name |
| Paid | SurfSense's paid plugins are unlocked by the SurfSense license key, which reaches only SurfSense's servers and is checked there on every call, never in the app. A third party bills on its own side and never sees the key ([`core/05-paid.md`](core/05-paid.md)) |
| License of SurfSense's plugin code | The folder decides it: `proprietary/` is Business Source License, everything else Apache-2.0. Only SurfSense's maintainers change `proprietary/`, so SurfSense holds all of its copyright. Price is the plugin's `access`, a separate question ([`core/05-paid.md`](core/05-paid.md#which-license-a-surfsense-plugin-is-under)) |
| SurfSense's own plugin servers | In `plugins/remote/` (Apache-2.0) and `plugins/remote/proprietary/` (Business Source License 1.1), all run by one plugin host on Azure Container Apps at `plugins.surfsense.com`, which also serves the registry ([ADR 0054](../../adr/0054-surfsenses-plugins-run-on-one-plugin-host.md), [`remote/02-surfsense-servers.md`](remote/02-surfsense-servers.md)) |
| `surfsense_mcp` | Stays the MCP server for outside clients. The app does not use it; SurfSense's plugins are their own servers |
| Offline | The app works with no plugin. Plugins are the one optional layer that connects out, and the interface says so: "SurfSense works offline. Plugins are optional and connect to the services you choose." Organisation policy can turn them off ([`core/04-trust.md`](core/04-trust.md#organisation-policy)) |

## Workstreams

| Stream | Owns | Needs |
|---|---|---|
| **Plugin lists** | `modules/plugins/lists/`: the first-party list and the app's fetched, cached copy of the registry; `plugins/registry/plugins.json`, the entry schema and the CI check for both, signing the registry | the plugin host, to serve the signed registry |
| **MCP client** | `modules/plugins/remote/`: the MCP client over Streamable HTTP, sign-in, `RemoteMcpSource` | nothing |
| **Gateway** | `modules/plugins/gateway/`, `installed/`, `routes.py`, the tables, readiness and approval rules, permissions | the MCP client |
| **Screen** | `frontend/src/features/plugins/`: Settings → Plugins, Connect, allowing third-party plugins, permissions, activity | the gateway's routes; can start against their shapes |
| **opencode** | `modules/agent/plugin_tools/`: the plugin servers and per-tool rules each turn gives opencode, and the listing check for changed tools | the gateway's readiness and approval rules, the MCP client |
| **`@` mentions** | The agent composer's `@` list, and the mention in `modules/agent/plugin_tools/` | the opencode endpoint |
| **Plugin host** | `plugins/remote/host/` and `plugins/remote/mcp_server/`: the one container on Azure Container Apps, its image, its deployment, Redis and SearXNG | nothing |
| **SurfSense scrapers** | `plugins/remote/proprietary/`: the scraping code copied out of `surfsense_backend`, its MCP tools, the license check | the plugin host; the root `LICENSE` line for `plugins/remote/proprietary/` |
| **Contributor guide** | [`plugins/README.md`](../../../plugins/README.md), rewritten: building a remote MCP server, trying it with a custom plugin by URL, the registry pull request | the registry's rules |
| **Bundles** | [`bundles/`](bundles/README.md) | deferred |

**Demo:** a thread on a tool-calling model connects a test remote server added as a custom plugin by URL, the agent calls one of its tools, and the result shows as a step.

**Ship:** Settings → Plugins lists SurfSense's plugins with no network and the registry once third-party plugins are allowed, a user connects SurfSense Scrapers with a trial license and a partner plugin with OAuth, the agent and `@` mentions use them, and the third-party switch, approval and Save to Sources work.

## Order of work

1. **License mode on the scraper API** ([contract 2](../../contracts/02-scraper-api-auth.md)), in `surfsense_backend`, for outside clients such as `surfsense_mcp`, whose personal keys are purged on 18 Oct 2026. It starts at once and in parallel; the plugins do not depend on it.
2. **The agent calls plugins**: the MCP client, the gateway, the tables, the `/plugins` routes, and each turn giving opencode the ready plugin servers and their rules, shown with a test server added as a custom plugin by URL.
3. **Steps tied to their calls**: each plugin step names its plugin and tool, shows the whole result, and offers Save to Sources.
4. **Settings → Plugins**: Connect, egress consent for every host at once, allowing third-party plugins, tool switches, activity.
5. **`@` mentions** in agent threads.
6. **The plugin lists and sign-in**: the first-party list, the registry, their check, signing and publishing the registry to SurfSense's host, the app's fetch and cache; OAuth; a connection kept open per plugin; progress on the screen.
7. **The plugin host and SurfSense Scrapers** on it ([`remote/02-surfsense-servers.md`](remote/02-surfsense-servers.md)). Then partners' entries.
8. **Scale**: the 24 a thread lists ranked by use, finding tools beyond them, tools that run as jobs ([`core/06-later.md`](core/06-later.md)).
9. **The chat engine's router step**, when plugins reach Basic threads, with the chat eval's router test ([`core/03-engines.md`](core/03-engines.md#the-chat-engine-later)).
10. **Bundles**, when something needs them.

## What this design gives up

Against the earlier design, where plugins ran locally from reviewed code:

- **Offline use of plugins.** A remote plugin needs the network. The app itself still works offline, and bundles bring offline plugins back later.
- **Data staying on the machine.** Each call's arguments go to the plugin's publisher. Consent per host, the privacy policy shown before Connect, and approval with the exact arguments make that visible.
- **Seeing the code.** SurfSense reviews a listing, not the server behind it, which can change at any time. Tools added or changed later start off, and a plugin can be delisted.
- **Availability.** A plugin stops working if its publisher's server does.
- **Some checks, for the agent's speed.** The agent's opencode calls plugin servers itself, so SurfSense checks the host on each connection, through the proxy opencode's traffic leaves by, rather than on each call, and descriptions reach the model uncut once a tool is reviewed.
- **Plugins in Basic threads, for now.** Only Agentic threads have plugins, and Agentic mode is offered only for models tested with opencode, so a user on a chat-only model waits for the chat engine's router step.

In return, the agent calls plugins and gets live results, existing MCP servers become plugins with one pull request, publishers update without app releases, and there is far less for SurfSense to build before the first plugin ships.

## What happens to the code already built

The local runner, the SDK, the CLI and the manifest rules in [`plugins/bundles/core/`](../../../plugins/bundles/core/) and [`modules/plugins/bundles/`](../../../surfsense_local/backend/modules/plugins/bundles/) were built for the earlier design. They sit in those `bundles/` folders, unwired, as the base for bundles: the runner becomes the bundle host, the SDK's `@action` becomes `@tool`. `document_metadata` on notes and the `api-url` file stay in use. [`bundles/README.md`](bundles/README.md) lists what changes when bundles are picked up. The earlier design's contributor guide moved with them to [`plugins/bundles/README.md`](../../../plugins/bundles/README.md); [`plugins/README.md`](../../../plugins/README.md) is rewritten by the contributor guide stream.

## Out of scope

Plugins that change SurfSense itself (providers, interface, prompts); a sandbox; payments for third parties; plugin-authored interface. Local MCP servers are an [open question](#open-questions).

## Open questions

- **Whether to run local MCP servers**, those started by a command such as `npx -y @modelcontextprotocol/server-filesystem` or `uvx mcp-server-git`, which most of the MCP ecosystem is today. opencode runs them already (`type: "local"`, a command and its environment), so calling one is the small part. The rest is a decision about what SurfSense promises:
  - **Trust.** The command downloads code and runs it with the user's permissions; approving each tool call does not limit a program already running. Claude Desktop and Cursor accept this for users who ask for it.
  - **The network fence.** The program inherits opencode's proxy variables, so `npx` and `uvx` cannot download and most such servers fail to start. Making them work means giving them their own environment, which leaves the program outside egress consent altogether, since the proxy only holds what respects it.
  - **Listing.** The rules for tools added later need SurfSense's own listing, with annotations, so SurfSense would start the command itself to list it; opencode's tool list carries none, which would leave every tool asking.
  - **One copy per thread.** Each thread's opencode instance starts its own process, so six open threads run six copies; a shared copy reached over HTTP would need a small bridge.
  - **What is installed.** `npx` needs Node and `uvx` needs uv, neither shipped, so a missing one has to read as that rather than as a broken plugin.

  The smallest version that keeps the promise honest is an advanced **Run a command** kind, off by default: the exact command and its environment variables, encrypted as keys are, shown and confirmed before it first runs, with a warning that it can reach anything the user can and that Settings › Network does not cover it. The alternative is to leave local plugins to [bundles](bundles/README.md), which run pinned code without `npx` at runtime.
- The citation a chat answer gives a tool result, beside today's chunk citations.
- How long tool results are kept and how large a stored one may be.
- Whether outside clients, `surfsense_mcp` and direct users of the scraper API, move to the plugin host once the backend's scraper API is retired.
