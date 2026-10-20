---
status: proposed
code:
  - surfsense_local/backend/modules/plugins/
  - surfsense_local/backend/modules/chat/plugin_router/
  - plugins/remote/
  - plugins/bundles/
---

# Plugins: what is not built

> Remote plugins are built: SurfSense's own on the [plugin host](../../architecture/plugin-host.md), third-party ones in the signed [registry](../../architecture/plugin-registry.md), any server by URL, called by the agent's opencode under rules SurfSense writes each turn ([plugins](../../architecture/plugins.md), [agent](../../architecture/agent.md#plugins)). This page holds what comes next, roughly in the order it is likely to be needed. Any remote MCP server connects with the sign-in it uses, a key in any header or OAuth with the user's own app included ([ADR 0063](../../adr/0063-a-plugins-connection-is-a-transport-and-one-sign-in.md)). Plugins that run on the user's machine are [bundles](bundles/README.md), deferred.

The decisions behind what is built are ADRs [0051](../../adr/0051-plugins-are-mcp-servers-behind-one-tool-gateway.md), [0053](../../adr/0053-plugins-are-listed-in-a-registry-and-third-party-ones-start-off.md) and [0054](../../adr/0054-surfsenses-plugins-run-on-one-plugin-host.md); the one behind the router step below is [ADR 0052](../../adr/0052-the-chat-model-never-calls-tools.md).

## Kept so later work stays additive

| Extension point | Where | Why |
|---|---|---|
| `kind` on every list entry | `remote` today, `bundle` later ([registry](../../architecture/plugin-registry.md#the-entry-rules)) | A bundle joins both lists behind the same Connect |
| `schema_version` and ignored unknown fields | [registry](../../architecture/plugin-registry.md#the-entry-rules) | New fields reach new apps without breaking old ones |
| The gateway's `ReadyTool`, with `qualified_name` (`<plugin>__<tool>`) and `exposure` | [plugins](../../architecture/plugins.md#ready-tools) | The chat engine and a tool search read them; nothing does yet |
| Permissions per plugin and tool | [plugins](../../architecture/plugins.md#ready-tools) | Not tied to how a plugin runs |

## The chat engine's router step

Plugins reach Basic threads, so every model the chat engine runs can use them, not only those tested with opencode. The chat model never calls a tool ([ADR 0052](../../adr/0052-the-chat-model-never-calls-tools.md)): SurfSense asks it two small questions, each held to a JSON schema, then makes the call itself. In `modules/chat/plugin_router/`:

1. **Choose.** One call with the user's message, the last exchange, and each candidate tool's name, title and description, cut to 2,000 characters, held to `{"tool": <enum of the candidates, plus "none">}`, thinking off. `none` ends the router. Candidates are ready `direct` tools with a flat input schema that are not `destructiveHint: true`.
2. **Fill.** One call held to the chosen tool's input schema. A required field it cannot fill ends the router.
3. **Call.** The gateway's `call_tool` with `caller: chat_router`, a 60-second deadline, and the same approval as the agent.
4. **Answer.** The result joins the final user message as a labelled block after the retrieved passages, so the prompt grows only at its end ([ADR 0049](../../adr/0049-prompts-grow-at-the-end.md)). Then the normal answer call runs.

A reply that does not match its schema counts as `none` (choose) or ends the router (fill); a router call that fails skips it. Whenever the router ends early, the turn answers as it does today. Router calls go through the same route and admission as any model request ([ADR 0048](../../adr/0048-the-api-is-the-only-path-to-a-text-model.md)) and count against a ChatGPT plan.

What it brings, since the chat engine has no opencode session to keep its calls:

- **`plugin_calls`**: one row per call, with its workspace, thread and message, caller, plugin and tool, arguments, status (`waiting_approval`, `running`, `succeeded`, `failed`, `denied`, `cancelled`), the whole result and any error. No foreign key to the plugin, so a past call stays in its thread after a disconnect.
- **The gateway's `call_tool`**: arguments checked against the tool's schema, approval from the caller, the call recorded, the result trimmed to 20 KB for the model and stored whole, a source's failure a sentence and never an exception.
- **The client's calls**: progress passed up, a deadline that tells the server to stop, and a call never resent, since the server may have acted.
- **Connections kept open** per plugin, dropped after ten minutes idle, so its calls skip a handshake. A holder task, since the SDK's tasks must close where they opened.

**When the router is on.** The [chat eval](../chat-eval.md) gains a router test: questions with the right tool or `none` and the right inputs, run on every curated model. The first row that matches the selected model wins.

| The selected model | Router |
|---|---|
| `structured_output: false` in the catalog | Never |
| Three router replies in a row that did not match their schema | Off, with a notice; the user can turn it back on |
| Failed the router test | Off by default |
| Passed the router test | On by default |
| Remote, with `structured_output: true` in the catalog, or a ChatGPT plan's model | On by default |
| Anything else | Off by default; Settings → Plugins offers "Let the chat use plugins on its own" |

**`@` in chat threads.** A mention skips choose. Where the router is on, the model fills the inputs; where it is off, or a fill fails its schema, the composer shows the tool's inputs as a form, filled from the message where it can be. A form the user completed is their approval for that one call, unless the tool is `destructiveHint: true`.

## Long calls as jobs on the plugin host

The proxies in front of a server end a request after 100 to 240 seconds, and MCP progress does not lift their limit, so a call to SurfSense's plugins that can run past three minutes becomes a job.

- **Jobs are ordinary tools**, not MCP tasks, which opencode does not use: `crawl_site(...)` queues and answers `{job_id, status: "running"}`, `get_job(job_id)` answers status, progress and the result or a page of it, `cancel_job(job_id)` stops it.
- **A job runner in every copy of the host** takes jobs from Redis under the copy's own limit, records a heartbeat, and runs a job whose copy died once more before failing it.
- **A job is its license's**, kept under a hash of the key; any other license is told no such job exists.
- **A large result is a finished job**, paged by `get_job`.
- **Kept a day**: the job in Redis (persistence on), its result in a private object-storage bucket with a lifecycle rule. No database: everything expires within a day and is read by its key.
- **Shared state in Redis** too: requests and rate limits per license, and per IP address for a free plugin; license answers and the 24-hour grace, so a deploy during a Keygen outage locks out no one.

## Scaling the plugin host

Copies of the one container are added once their load, memory above all since browsers fill it, passes a threshold set below each copy's own browser limit, so a new copy starts before a call queues; at least one always runs. Each plugin also gets its own limit on threads and browsers. A plugin whose load dwarfs the rest runs apart with `PLUGINS=<id>` behind a path rule, as already possible ([plugin host](../../architecture/plugin-host.md#adding-a-plugin)).

## More from MCP

| Addition | What it gives | What it takes |
|---|---|---|
| **`list_changed`** | A changed tool seen when the server says so, not at the next check | A kept connection to listen on |
| **Ranking the 24** | The tools a thread lists chosen by recent use, not by when each plugin was connected | A count of each tool's recent calls |
| **Finding tools on demand** | Plugins beyond the 24, through a search tool, as Pi's `tool_search` does | `exposure: deferred`; a `find_plugin_tools` tool, and a way to call what it finds without breaking the prompt cache |
| **Prompts and resources** | A server's prompts as composer shortcuts; its resources to browse and save to Sources | Two more parts of the MCP client and two screens |
| **Elicitation** | A server asking the user a question mid-call | A dialog, a rule on what a server may ask, and a session the plugin host does not keep today |
| **Sampling** | A server asking to use the user's own model | The model route and a limit on what it may spend |
| **Long-running third-party tools** | Tools that run past a call's 200 seconds | `job` tools on the `plugins` queue, and paging a large result |
| **Skills on a plugin** | A `SKILL.md` folder on an entry teaching the agent to use its tools well | A `skills` field, and opencode's `skills.paths` and `skill` permission, as SurfSense's own skills reach it |
| **Sync and schedules** | A tool run on a schedule, its result kept in Sources and updated in place | A scheduler, and the `plugins` queue for the runs |

## Organisation policy

Enterprise settings that turn plugins off, keep third-party plugins off, or allow a fixed list of plugin ids. `list_tools()` is the one place that would read them, so the agent, the screen and a later chat engine all follow. A company's own registry beside SurfSense's comes the same way: an administrator setting, never a user's click, so a link cannot add one.

## Elsewhere

- **A public directory page** on surfsense.com, generated from both lists. Today `surfsense.com/plugins` is a hand-written list of the scraper platforms.
- **Paid bundles**: a SurfSense paid plugin that runs locally, delivered by the license server ([ADR 0047](../../adr/0047-premium-plugins-are-source-available.md), [bundles](bundles/README.md)).
- **Deleting the backend's scraping code** once its scraper API is retired, never before the purge on 18 Oct 2026 ([plugin host](../../architecture/plugin-host.md#layout)).

## Local MCP servers

Decided on 20 Oct 2026: a server started by a command, such as `npx -y @modelcontextprotocol/server-filesystem` or `uvx mcp-server-git`, is not added as a custom plugin. Plugins stay remote MCP servers; local ones come with [bundles](bundles/README.md), whose design is to be redone first. opencode runs such servers already (`type: "local"`), so calling one is the small part. What kept them out is what SurfSense promises:

- **Trust.** The command downloads code and runs it with the user's permissions; approving each call does not limit a program already running.
- **The network fence.** The program inherits opencode's proxy variables, so `npx` and `uvx` cannot download and most such servers fail to start. Giving them their own environment leaves them outside egress consent altogether.
- **Listing.** The rules for tools added later need SurfSense's own listing, with annotations, so SurfSense would start the command itself to list it.
- **One copy per thread.** Each thread's opencode instance starts its own process; a shared copy over HTTP needs a small bridge.
- **What is installed.** `npx` needs Node and `uvx` needs uv, neither shipped, so a missing one has to read as that, not as a broken plugin.

## Open questions

- The citation a chat answer gives a tool result, beside today's chunk citations.
- How long the chat engine keeps tool results, and how large a stored one may be.
- Whether outside clients, `surfsense_mcp` and direct users of the scraper API, move to the plugin host once the backend's scraper API is retired.
