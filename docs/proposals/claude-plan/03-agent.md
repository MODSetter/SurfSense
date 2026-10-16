# The agent on a Claude plan

> A Claude plan reaches the user only through Claude Code, and Claude Code runs its own agent loop: it cannot be one more model behind opencode's provider. So an agent turn on a Claude plan model runs Claude Code as a second engine, in the API process, behind an engine interface that opencode moves behind first. SurfSense keeps what makes the agent SurfSense's: the thread folder, its tools and plugins, its permission rules, its frames and its approval screen.

Part of [Use your Claude plan](README.md). How opencode runs today is in [agent](../../architecture/agent.md).

## Why not opencode

opencode reaches a model through an HTTP provider, and every model reaches it through SurfSense's model endpoint ([agent](../../architecture/agent.md#the-model-endpoint)). A Claude plan has no HTTP endpoint SurfSense may call: the only way in is Claude Code. Community providers that wrap Claude Code for the AI SDK exist, but they ignore the caller's tools ("AI SDK tools passed to `generateText`/`streamText` via the `tools` option are ignored", [ai-sdk-provider-claude-code](https://github.com/ben-vargas/ai-sdk-provider-claude-code)) and leave permissions to Claude Code, so opencode would only display a loop it does not run.

## The engine interface

[`modules/agent/engines/`](../../../surfsense_local/backend/modules/agent/engines/) holds a protocol, [`AgentEngine`](../../../surfsense_local/backend/modules/agent/engines/agent_engine.py), with what the chat, permission, step and workspace routes ask of the agent, and opencode's existing code is its first implementation, [`OpencodeEngine`](../../../surfsense_local/backend/modules/agent/engines/opencode_engine.py), with no change in behaviour (step 3 of the [build order](README.md#build-order), built). The routes reach an engine only through [`thread_engine()`](../../../surfsense_local/backend/modules/agent/engines/thread_engine.py):

| Method | opencode |
|---|---|
| `open_session(session, thread, launch_key) -> bool` | [`open_session.py`](../../../surfsense_local/backend/modules/agent/agent_threads/open_session.py), then records `opencode_session_id` |
| `run_turn(session, thread, payload, launch_key, place)` | `agent_turn` in [`turn.py`](../../../surfsense_local/backend/modules/agent/agent_threads/turn.py) |
| `thread_messages(session, thread, launch_key, answering)` | `agent_thread_messages` |
| `answer_permission(thread, request_id, reply)` | opencode's `reply` |
| `stored_step(thread, part_id)` | a step whole, for its result and Save to Sources |
| `forget_thread(thread)`, `forget_workspace(session, workspace_id)` | `forget_sessions.py` |

Stop is not a method: the stop route stops the thread's run, and the engine's turn, which watches its run, ends itself, as opencode's aborts its session.

[`ChatThread`](../../../surfsense_local/backend/modules/chat/models.py) gains `agent_engine` (`opencode` or `claude_code`, `NULL` for a chat thread), `claude_session_id`, and `claude_account`, the Claude Code account that session was made under. `opencode_session_id` stays. A thread that has switched engines holds both ids ([`04-handover.md`](04-handover.md)).

Before each turn, the selected model's connection picks the engine: `claude_plan` is `claude_code`, anything else `opencode`. When it differs from `agent_engine`, the handover runs and `agent_engine` changes.

[`engine_choice.py`](../../../surfsense_local/backend/modules/agent/engine_choice.py): a Claude plan model passes the technical gates when its connection's status is `ready`. It needs no opencode staged, states tool calls, and every listed model's window is above 32,768 tokens.

## A turn

The thread's folder is synced to its sources and the scope note written exactly as for opencode ([agent](../../architecture/agent.md#the-ticked-sources)). Then `launch.py` starts, or resumes, a client with:

| Option | Value |
|---|---|
| `model` | the model's `value` |
| `cwd` | the thread's working folder (`thread_working_dir`) |
| `tools` | `["Read", "Glob", "Grep", "Write", "Edit", "Skill"]`. No `Bash` ([ADR 0039](../../adr/0039-document-scripts-run-without-approval.md)), no `WebFetch` or `WebSearch`, no `Task` subagents, no `NotebookEdit` |
| `mcp_servers` | the path of a file only the user can read, removed when the client closes, holding `surfsense`: the thread's [tool endpoint](../../../surfsense_local/backend/modules/agent/tool_endpoint/) as `{"type": "http", "url": …, "headers": {"Authorization": "Bearer <launch key>"}}`, the same endpoint opencode calls; and each ready plugin under its id, with its sign-in header, as [`give_plugins.py`](../../../surfsense_local/backend/modules/agent/plugin_tools/give_plugins.py) builds them. Given as a dict, the SDK puts it on Claude Code's command line, where any process on the machine can read the headers |
| `disallowed_tools` | every tool of a given plugin that the gate denies, so the model is never offered it, as opencode's `deny` leaves a tool out |
| `plugins`, `skills` | SurfSense's skills folder as a local plugin, `surfsense`, and `skills` naming its skills (`surfsense:documents`, …), which hides Claude Code's own skills from the model |
| `env` | `MAX_MCP_OUTPUT_TOKENS` above the largest result SurfSense's tools return: over Claude Code's default of 25,000 tokens, a result is written to a file under `~/.claude/projects` and the model told to read it, which the gate refuses |
| `system_prompt` | SurfSense's agent prompt. The scope note and any handover note travel beside the user's message ([`04-handover.md`](04-handover.md#where-the-note-goes)) |
| `hooks` | `PreToolUse`: [the gate](#the-gate) |
| `can_use_tool` | the gate again |
| `thinking` | `{"type": "adaptive", "display": "summarized"}` when the thread's thinking switch is on |
| `include_partial_messages` | `True` |
| `session_store` | SurfSense's store ([Sessions](#sessions)) |
| `resume` | `claude_session_id`, after the first turn |

The plugin steps before a turn (sign-ins, the license, changed tools, the servers) run unchanged ([agent](../../architecture/agent.md#plugins)); what they produce is passed as `mcp_servers`, `disallowed_tools` and to the gate, instead of to opencode's session.

**Network.** Claude Code connects to each plugin server itself, as opencode does, so an agent run's `HTTPS_PROXY` is an agent proxy, separate from chat's: it passes `api.anthropic.com` and `platform.claude.com` while their destinations are on, and a ready plugin's hosts by the check the plugin proxy applies to opencode ([ADR 0059](../../adr/0059-claude-code-reaches-anthropic-and-in-the-agent-the-turns-plugins.md)). A chat run keeps the Claude proxy, which passes no plugin host. Forwarding plugin calls through the tool endpoint instead was rejected: SurfSense has no MCP client of its own to forward with, and opencode already holds plugin headers.

**Clients.** `mcp_servers`, `disallowed_tools` and the skills are fixed when Claude Code starts. Each turn's are digested, as [`given_servers.py`](../../../surfsense_local/backend/modules/agent/plugin_tools/given_servers.py) digests opencode's servers: a thread's running client is reused while the digest matches, and otherwise closed and its session resumed with the new ones. A plugin whose tools changed is reconnected (`reconnect_mcp_server`), which starts a new MCP session, as giving it to opencode again does. The gate reads the rules on every call, so a client launched under older rules still cannot run a tool now denied.

Measured: Claude Code connected to an HTTP MCP endpoint behind a bearer key and every call carried it; the init message listed only the passed tools. With `mcp_servers` as a dict, the plugin's key was in the process's arguments; as a file path, it was not. `disallowed_tools`, wildcards included, left those tools out of the init message. A remote plugin's MCP traffic reached the proxy as `CONNECT plugin.example.com:443`. A tool added to a server mid-session was not seen until `reconnect_mcp_server`, then seen in the same session. SurfSense's skills folder given as a local plugin was listed as `surfsense:documents`, loaded through `Skill` and followed, with `verbatim_prompts` on and off. A 59,000-character MCP result was written to a file under `~/.claude/projects` instead of reaching the model.

## Same as opencode

A Claude plan model in Agentic does everything an opencode model does, through the same code where SurfSense owns it:

| Capability | opencode | Claude Code |
|---|---|---|
| SurfSense's tools: search, read a document, source pages, images, artifacts, render, revise, convert, analyze data, PDF pages, stamp and form | the thread's tool endpoint | the same endpoint, as `mcp__surfsense__<tool>` |
| Reading sources | `read`, `glob`, `grep`, `list` in `sources/` | `Read`, `Glob`, `Grep`, held to the folder by the gate |
| Writing | `outputs/` only | `outputs/` only |
| Skills: documents, revisions, data, PDF | the skills folder | the same folder as a local plugin, and `Read` inside it |
| Plugins: up to 24 ready tools and any mentioned, sign-ins, the license, `allow`, `ask`, `deny` | `turn_plugins()`, given to opencode | `turn_plugins()`, in the MCP file, `disallowed_tools` and the gate |
| A plugin call on SurfSense's plugin host: calls token, text-only results, 300 s, Stop cancels it | headers on the server, opencode's timeout, `POST /cancel` | the same headers, `MCP_TOOL_TIMEOUT`, the same cancel |
| A step's whole result, Save to Sources | opencode's stored session | SurfSense's mirrored entries |
| Bash, web, subagents, questions | denied | not given |

Code written for opencode that changes so both engines get it:

- The tool endpoint hides image-returning tools from a model that cannot see images by reading opencode's `opencode.json`. It asks the thread's model instead.
- A tool call's timeout, 200 s, or 300 s on SurfSense's plugin host, is opencode's per-server setting. Claude Code's is `MCP_TOOL_TIMEOUT`, set to the longer.

One suite of scenarios runs against both engines: search and cite, read `sources/`, write `outputs/` and be refused outside it, render a Word document, an allowed, an approved and a hidden plugin tool, Stop during a plugin call, and Save to Sources.

## The gate

Claude Code 2.1.301 starts in `auto` permission mode, and in `auto` it approved and ran an MCP `delete_note` without calling `can_use_tool`. `launch.py` therefore forces `permission_mode="default"`, and the decision lives in a `PreToolUse` hook, which ran before every call in every mode measured. `can_use_tool` applies the same rules, so a future mode that skips one still meets the other.

The rules are opencode's ([`opencode_config.py`](../../../surfsense_local/backend/modules/agent/opencode_config.py) `_permission()`, and the per-session plugin rules), read from the same sources:

| Tool | Rule |
|---|---|
| `Read`, `Glob`, `Grep` | allow inside the thread's folder and the skills folder; deny `AGENTS.md`, `CLAUDE.md`, `.opencode/` and anything outside |
| `Write`, `Edit` | allow under the thread's `outputs/`; deny everything else |
| `mcp__surfsense__*` | allow |
| `Skill` | allow a `surfsense:` skill; deny any other |
| `mcp__<plugin>__<tool>` | the gateway's `allow` or `ask` for a ready tool; deny a tool switched off, unreviewed or on a server not given this turn |
| anything else | deny |

A path is resolved against `cwd` with symlinks followed before it is compared. Measured with these rules: `sources/plan.txt` read and `outputs/summary.md` written; `../escaped.txt` and `/tmp/escaped2.txt` refused; a `CLAUDE.md` placed in the folder not loaded, since `setting_sources` is `[]`. An `allow` ran a plugin tool, an `ask` reached `can_use_tool` before the call, and a `deny` stopped it with the hook's reason given to the model. A PNG in the folder read with `Read` reached the model as an image, and `/etc/hosts` was refused.

**Ask.** The hook emits a `permission-request` frame (`id`, `permission` as the tool's display name, `patterns`, `call_id` from the hook's `tool_use_id`), sets the run to `needs-approval`, and awaits the answer from `answer_permission`: `once` returns `permissionDecision: "allow"`, `reject` returns `deny` with "The user rejected this action." Never "always" ([ADR 0028](../../adr/0028-model-written-code-runs-with-approval.md)). Measured: a hook that awaited an answer 1 to 1.5 s later held the call, and a rejected call never reached the server.

## Frames

`engines/claude_code/frames.py` turns SDK messages into the frames [`turn_frames.py`](../../../surfsense_local/backend/modules/agent/agent_threads/turn_frames.py) emits for opencode, so the frontend changes nothing:

| SDK message | Frame |
|---|---|
| `system` `init` | `accepted` |
| `content_block_delta` `text_delta` | `delta` |
| `content_block_delta` `thinking_delta`, then the block's stop | `reasoning`, `reasoning-end` |
| `content_block_start` `tool_use`, `AssistantMessage` `ToolUseBlock` | `agent-step`, `running`, with `call_id` |
| `UserMessage` `ToolResultBlock` | `agent-step`, `completed` or `error`, `output` up to 4,000 characters |
| the gate asking | `permission-request`; its answer `permission-replied` |
| `ResultMessage` success | `completed`, with the reply's text joined and citations resolved as for opencode |
| `ResultMessage` error, `AssistantMessage.error` | `error`, kind from [`01-connection.md`](01-connection.md#errors) |
| `RateLimitEvent` not `allowed` | `error`, `subscription_limit` |
| `system` `compact_boundary` | none: the turn goes on ([Sessions](#sessions)) |

A tool's name maps back to what a step shows: `mcp__surfsense__render_document` is `surfsense_render_document`, and `mcp__<plugin>__<tool>` reads as the plugin's name and the tool's title, as `steps.py` does for opencode's `<plugin>_<tool>`.

One test runs the same scripted turn through both engines and compares their frames, so the frontend never sees the two drift.

## Stop

Stop calls `interrupt()` and records `stopped` against the reply in SurfSense's store, as Stop notes itself in opencode's session metadata today ([chat](../../architecture/chat.md#how-an-agent-reply-ended)). Measured: `interrupt()` returned in 0.01 s, the turn ended `error_during_execution`, and the same client answered the next message. Quit closes every client.

## Sessions

Claude Code keeps a session's transcript as JSONL under `~/.claude/projects/<folder key>/<session id>.jsonl`. That folder is not SurfSense's, as opencode's database, under SurfSense's data folder, is:

- Claude Code deletes transcripts older than `cleanupPeriodDays`, 30 by default, whenever it starts, the user's own runs included.
- The user may clear `~/.claude`, reinstall Claude Code, or move to another machine; a backup of SurfSense's data holds none of it.
- Its format is Claude Code's and changes with it; `SessionStore` is the SDK's interface for keeping it elsewhere.

So SurfSense mirrors it through the SDK's `SessionStore` protocol into its own table, `claude_session_entries` (session id, entry uuid, order, JSON), so:

- **Listing** reads the thread from SurfSense's table, not from `~/.claude`: each user turn, then one reply with `content.text`, `content.steps` and `content.citations`, as opencode's listing returns.
- **Reopening** a thread resumes `claude_session_id` with the store. Measured: resuming from a store after the local file was deleted remembered the earlier turn.
- **Deleting** stops the run, deletes the thread's entries and its local transcript file.

Persistence stays on for agent sessions: with `--no-session-persistence`, resume found no conversation even with a store.

Claude Code compacts a full window itself, mid-turn included. Its compaction boundary is folded into the turn it happened in, as [`compaction.py`](../../../surfsense_local/backend/modules/agent/agent_threads/compaction.py) folds opencode's. Measured with the window forced to 100,000 tokens, its floor: a `PreCompact` hook, a `status` of `compacting`, then a `compact_boundary` with `pre_tokens` 69,221 and `post_tokens` 5,130, after which the same turn went on; no summary reached the reply, and a fact from the first turn was still known.

## Keeping up with Claude Code

Claude Code updates itself on the user's machine, so each behaviour this engine relies on is a test under `claude_code` against the installed binary: the gate in `default` mode, `disallowed_tools` hiding a tool, the MCP file kept off the command line, plugin traffic through the proxy, skills through `plugins`, the result size limit, and `compact_boundary`'s shape. The engine refuses a Claude Code older than the lowest version those tests passed on, as the connection does ([`01-connection.md`](01-connection.md#status)).

## Open questions

- That `skills` keeps the model from calling Claude Code's own skills: the init message still lists them.
- Whether local transcripts are deleted once mirrored, or kept as Claude Code's own history.
