# The agent on a Claude plan

> A Claude plan reaches the user only through Claude Code, and Claude Code runs its own agent loop: it cannot be one more model behind opencode's provider. So an agent turn on a Claude plan model runs Claude Code as a second engine, in the API process, behind an engine interface that opencode moves behind first. SurfSense keeps what makes the agent SurfSense's: the thread folder, its tools and plugins, its permission rules, its frames and its approval screen.

Part of [Use your Claude plan](README.md). How opencode runs today is in [agent](../../architecture/agent.md).

## Why not opencode

opencode reaches a model through an HTTP provider, and every model reaches it through SurfSense's model endpoint ([agent](../../architecture/agent.md#the-model-endpoint)). A Claude plan has no HTTP endpoint SurfSense may call: the only way in is Claude Code. Community providers that wrap Claude Code for the AI SDK exist, but they ignore the caller's tools ("AI SDK tools passed to `generateText`/`streamText` via the `tools` option are ignored", [ai-sdk-provider-claude-code](https://github.com/ben-vargas/ai-sdk-provider-claude-code)) and leave permissions to Claude Code, so opencode would only display a loop it does not run.

## The engine interface

`modules/agent/engines/` gets a protocol with the five things the chat router asks of the agent today, and opencode's existing code becomes its first implementation with no change in behaviour (step 3 of the [build order](README.md#build-order)):

| Method | opencode today |
|---|---|
| `open_session(thread)` | [`open_session.py`](../../../surfsense_local/backend/modules/agent/agent_threads/open_session.py) |
| `run_turn(thread, message, model, scope) -> frames` | `agent_turn` in [`turn.py`](../../../surfsense_local/backend/modules/agent/agent_threads/turn.py) |
| `thread_messages(thread)` | `agent_thread_messages` |
| `answer_permission(thread, request_id, verdict)` | the `/chat/threads/{id}/permissions/{request_id}` route |
| `stop(thread)`, `forget(thread)` | the run's abort and `forget_thread` |

[`ChatThread`](../../../surfsense_local/backend/modules/chat/models.py) gains `agent_engine` (`opencode` or `claude_code`, `NULL` for a chat thread), `claude_session_id`, and `claude_account`, the Claude Code account that session was made under. `opencode_session_id` stays. A thread that has switched engines holds both ids ([`04-handover.md`](04-handover.md)).

Before each turn, the selected model's connection picks the engine: `claude_plan` is `claude_code`, anything else `opencode`. When it differs from `agent_engine`, the handover runs and `agent_engine` changes.

[`engine_choice.py`](../../../surfsense_local/backend/modules/agent/engine_choice.py): a Claude plan model passes the technical gates when its connection's status is `ready`. It needs no opencode staged, states tool calls, and every listed model's window is above 32,768 tokens.

## A turn

The thread's folder is synced to its sources and the scope note written exactly as for opencode ([agent](../../architecture/agent.md#the-ticked-sources)). Then `launch.py` starts, or resumes, a client with:

| Option | Value |
|---|---|
| `model` | the model's `value` |
| `cwd` | the thread's working folder (`thread_working_dir`) |
| `tools` | `["Read", "Glob", "Grep", "Write", "Edit"]`. No `Bash` ([ADR 0039](../../adr/0039-document-scripts-run-without-approval.md)), no `WebFetch` or `WebSearch`, no `Task` subagents, no `Skill`, no `NotebookEdit` |
| `mcp_servers` | `surfsense`: the thread's [tool endpoint](../../../surfsense_local/backend/modules/agent/tool_endpoint/) as `{"type": "http", "url": …, "headers": {"Authorization": "Bearer <launch key>"}}`; and each ready plugin under its id, with its sign-in header, as [`give_plugins.py`](../../../surfsense_local/backend/modules/agent/plugin_tools/give_plugins.py) builds them |
| `system_prompt` | SurfSense's agent prompt. The scope note and any handover note travel beside the user's message ([`04-handover.md`](04-handover.md#where-the-note-goes)) |
| `hooks` | `PreToolUse`: [the gate](#the-gate) |
| `can_use_tool` | the gate again |
| `thinking` | `{"type": "adaptive", "display": "summarized"}` when the thread's thinking switch is on |
| `include_partial_messages` | `True` |
| `session_store` | SurfSense's store ([Sessions](#sessions)) |
| `resume` | `claude_session_id`, after the first turn |

The plugin steps before a turn (sign-ins, the license, changed tools, the servers) run unchanged ([agent](../../architecture/agent.md#plugins)); what they produce is passed as `mcp_servers` and to the gate, instead of to opencode's session. The proxy allows `api.anthropic.com` and each ready plugin's hosts, as `may_connect` already decides for opencode.

Measured: Claude Code connected to an HTTP MCP endpoint behind a bearer key and every call carried it; the init message listed only the passed tools.

## The gate

Claude Code 2.1.301 starts in `auto` permission mode, and in `auto` it approved and ran an MCP `delete_note` without calling `can_use_tool`. `launch.py` therefore forces `permission_mode="default"`, and the decision lives in a `PreToolUse` hook, which ran before every call in every mode measured. `can_use_tool` applies the same rules, so a future mode that skips one still meets the other.

The rules are opencode's ([`opencode_config.py`](../../../surfsense_local/backend/modules/agent/opencode_config.py) `_permission()`, and the per-session plugin rules), read from the same sources:

| Tool | Rule |
|---|---|
| `Read`, `Glob`, `Grep` | allow inside the thread's folder and the skills folder; deny `AGENTS.md`, `CLAUDE.md`, `.opencode/` and anything outside |
| `Write`, `Edit` | allow under the thread's `outputs/`; deny everything else |
| `mcp__surfsense__*` | allow |
| `mcp__<plugin>__<tool>` | the gateway's `allow` or `ask` for a ready tool; deny a tool switched off, unreviewed or on a server not given this turn |
| anything else | deny |

A path is resolved against `cwd` with symlinks followed before it is compared. Measured with these rules: `sources/plan.txt` read and `outputs/summary.md` written; `../escaped.txt` and `/tmp/escaped2.txt` refused; a `CLAUDE.md` placed in the folder not loaded, since `setting_sources` is `[]`.

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

A tool's name maps back to what a step shows: `mcp__surfsense__render_document` is `surfsense_render_document`, and `mcp__<plugin>__<tool>` reads as the plugin's name and the tool's title, as `steps.py` does for opencode's `<plugin>_<tool>`.

## Stop

Stop calls `interrupt()` and records `stopped` against the reply in SurfSense's store, as Stop notes itself in opencode's session metadata today ([chat](../../architecture/chat.md#how-an-agent-reply-ended)). Measured: `interrupt()` returned in 0.01 s, the turn ended `error_during_execution`, and the same client answered the next message. Quit closes every client.

## Sessions

Claude Code keeps a session's transcript as JSONL under `~/.claude/projects/<folder key>/<session id>.jsonl`. SurfSense mirrors it through the SDK's `SessionStore` protocol into its own table, `claude_session_entries` (session id, entry uuid, order, JSON), so:

- **Listing** reads the thread from SurfSense's table, not from `~/.claude`: each user turn, then one reply with `content.text`, `content.steps` and `content.citations`, as opencode's listing returns.
- **Reopening** a thread resumes `claude_session_id` with the store. Measured: resuming from a store after the local file was deleted remembered the earlier turn.
- **Deleting** stops the run, deletes the thread's entries and its local transcript file.

Persistence stays on for agent sessions: with `--no-session-persistence`, resume found no conversation even with a store.

Claude Code compacts a full window itself. Its compaction boundary is folded into the turn it happened in, as [`compaction.py`](../../../surfsense_local/backend/modules/agent/agent_threads/compaction.py) folds opencode's; this is untested.

## Open questions

- SurfSense's skills (documents, data, PDF) reach opencode as a skills folder. Whether the SDK's `plugins` option with a local path carries them to Claude Code unchanged, or the engine gives their instructions in the system prompt.
- Claude Code's compaction message in a long thread, and whether its summary leaks into the reply.
- Images the agent is shown ([agent](../../architecture/agent.md#image-input)): `Read` of an image file, untested.
- Whether local transcripts are deleted once mirrored, or kept as Claude Code's own history.
