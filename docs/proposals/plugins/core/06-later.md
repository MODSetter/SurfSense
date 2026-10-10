# Later

> What comes after remote plugins, and what this design fixes now so each arrives as an addition rather than a redesign. Nothing here is built until something needs it.

## Fixed now so later work stays additive

| Extension point | Where | Why |
|---|---|---|
| `kind` on every list entry | [`02-registry.md`](02-registry.md) | `bundle` joins `remote` in both lists, behind the same Connect button |
| `ToolSource` behind the gateway | [`01-architecture.md`](01-architecture.md#tool-sources) | A new kind of source is one more implementation; opencode, `@` mentions, approval and the chat engine's router do not change |
| `<plugin>__<tool>` names | [`01-architecture.md`](01-architecture.md#names) | Permissions, steps and history stay stable whatever the source |
| Permissions and consent per plugin and tool | [`04-trust.md`](04-trust.md) | Not tied to how a plugin runs |
| `schema_version` and ignored unknown fields | [`02-registry.md`](02-registry.md) | New fields reach new apps without breaking old ones |

## Roughly in the order they are likely to be needed

| Addition | What it gives | What it takes |
|---|---|---|
| **The chat engine's router step** | Plugins in Basic threads, so every model the chat engine runs can use them, not only those tested with opencode | `modules/chat/plugin_router/`, the chat eval's router test, `@` mentions with an input form in chat threads ([`03-engines.md`](03-engines.md#the-chat-engine-later), [ADR 0052](../../../adr/0052-the-chat-model-never-calls-tools.md)) |
| **Skills on a plugin** | A `SKILL.md` folder on a plugin's entry teaching the agent to use the plugin's tools well | A `skills` field; opencode's `skills.paths` and its `skill` permission allowlist, as SurfSense's own skills reach it ([agent](../../../architecture/agent.md)) |
| **Ranking the 24** | The tools a thread lists chosen by the user's recent calls, not by when each plugin was connected | A count of each tool's recent calls, from the threads' sessions or kept as calls are made |
| **Finding tools on demand** | Plugins beyond the 24 listed per thread, through a search tool, as Pi's `tool_search` does | `exposure: deferred`; a `find_plugin_tools` tool and a way to call what it finds without breaking the prompt cache |
| **Prompts and resources** | A server's prompts as composer shortcuts; its resources to browse and save to Sources | Two more parts of the MCP client and two screens |
| **Elicitation** | A server asking the user a question mid-call | A dialog, and a rule on what a server may ask |
| **Sampling** | A server asking to use the user's own model | The model route ([ADR 0048](../../../adr/0048-the-api-is-the-only-path-to-a-text-model.md)) and a limit on what it may spend |
| **Long-running tools** | Tools that run past a call's 190 seconds, such as a large crawl | `job` tools on the `plugins` queue, and paging a large result |
| **Connections kept open** | One session per plugin for SurfSense's own calls, dropped after ten minutes idle, instead of one per call: faster calls for the chat engine, and stateful plugins there. The agent's opencode keeps its own sessions already | A holder task, since the SDK's tasks must close where they opened |
| **Sync and schedules** | A tool run on a schedule, its result kept in Sources and updated in place | A scheduler, and the `plugins` queue for the runs |
| **Organisation policy** | Plugins off, third-party plugins locked off, or an allow-list | Enterprise settings the gateway reads ([`04-trust.md`](04-trust.md#organisation-policy)) |
| **Company registries** | A company's own list of plugins beside SurfSense's | An administrator setting, never a user's click, so a link cannot add one |
| **Bundles** | Plugins that run on the user's machine: offline and air-gapped use, local software, private processing, no hosting | [`bundles/`](../bundles/README.md): the bundle host, a bundled Python, a release Action for authors' repositories, the scanner that records each version's sha256 in the list ([`02-registry.md`](02-registry.md#bundle-entries-later)) |
| **Paid bundles** | A SurfSense paid plugin that runs locally | Delivery from the license server ([ADR 0047](../../../adr/0047-premium-plugins-are-source-available.md)) |
| **A public directory page** | Every plugin, its publisher, hosts and access, on the web | Generated from both lists |
