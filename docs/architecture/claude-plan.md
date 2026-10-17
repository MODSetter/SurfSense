# Claude plan

A Claude Pro, Max or Team subscriber picks **Use your Claude plan** and gets Claude's models in chat, titles, Studio and Agentic mode, paid for by their plan. SurfSense never signs in to Claude and holds no Claude credential: it drives the user's own installed, unmodified Claude Code through Anthropic's [Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview), and Claude Code keeps the sign-in. SurfSense ships no copy of Claude Code. Chat runs Claude Code with every tool off; Agentic mode runs it as a second engine beside opencode, with SurfSense's tools, rules, frames and approvals.

Every behaviour of Claude Code stated here was measured on 16 Oct 2026 on macOS arm64, against Claude Code `2.1.301` (native installer) on a Max plan, with the Python `claude-agent-sdk` `0.2.168`. Windows and Linux are untested on a real install (Known gaps).

**Code:** [`modules/llm/subscriptions/claude/`](../../surfsense_local/backend/modules/llm/subscriptions/claude/), [`modules/agent/engines/`](../../surfsense_local/backend/modules/agent/engines/), [`frontend/src/features/models/remote/connections/claude/`](../../surfsense_local/frontend/src/features/models/remote/connections/claude/)
**Decisions:** [ADR 0057](../adr/0057-a-claude-plan-runs-through-the-users-own-claude-code.md), [ADR 0061](../adr/0061-claude-code-reaches-anthropic-and-in-the-agent-the-turns-plugins.md), [ADR 0060](../adr/0060-one-consent-question-per-user-action.md), [ADR 0052](../adr/0052-the-chat-model-never-calls-tools.md), [ADR 0027](../adr/0027-egress-consent-per-host.md)

## How the user sees it

1. In **Settings › Add model** or onboarding's model step, **Use your Claude plan** sits beside **Use your ChatGPT plan**, offered wherever a plan fills the slot: text generation only. **Set up** opens a nested dialog.
2. The dialog shows what SurfSense found: Claude Code not installed, too old, signed out, or ready with the account's email and plan, and the one thing to do. Not installed, it lists installing, signing in with `claude` in a terminal, and coming back to press **Check again**, with **Open install guide**. Signing in happens in Claude Code, never in SurfSense.
3. **Add Claude models** asks for `api.anthropic.com` and `platform.claude.com` in one egress question, then lists Claude Code's models in every picker.
4. A Claude plan model then works in Basic and Agentic threads like any other; the user never picks an engine, and can switch a thread to another model and back.

## Finding Claude Code

[`locate.py`](../../surfsense_local/backend/modules/llm/subscriptions/claude/locate.py) returns the first `claude` that can run: each directory on the API's own `PATH`, then where Claude Code's installers put it, which a GUI app's `PATH` usually lacks:

| System | Searched after `PATH` |
|---|---|
| macOS, Linux | `~/.local/bin/claude` (native installer), `~/.claude/local/claude`, `~/.npm-global/bin/claude`, `~/.volta/bin/claude`, the newest `~/.nvm/versions/node/*/bin/claude`, `/opt/homebrew/bin/claude`, `/usr/local/bin/claude`, `/home/linuxbrew/.linuxbrew/bin/claude`, `/usr/bin/claude` |
| Windows | `%USERPROFILE%\.local\bin\claude.exe`, `%LOCALAPPDATA%\Microsoft\WinGet\Links\claude.exe`, `%APPDATA%\npm\node_modules\@anthropic-ai\claude-code\bin\claude.exe` |

On Windows only a `claude.exe` counts, since the SDK refuses npm's `claude.cmd`; elsewhere a file without the executable bit is passed over. The binary is found again before each run.

## Status

[`status.py`](../../surfsense_local/backend/modules/llm/subscriptions/claude/status.py) runs the binary twice, each with a 15-second timeout, the [launch environment](#launching-a-run) and its proxy, and on Windows `CREATE_NO_WINDOW`. A run that fails, times out or prints something unreadable counts as no answer.

| State | When | The dialog says |
|---|---|---|
| `not_installed` | no binary found | install Claude Code, sign in, come back and check again |
| `too_old` | `claude --version` below `MIN_VERSION`, 2.1.300, or unreadable | update Claude Code |
| `signed_out` | `claude auth status` reports `loggedIn: false`, or an `authMethod` other than `claude.ai`, since a Console login is not a plan | run `claude` and sign in |
| `ready` | signed in to a plan | connected as `email`, `subscriptionType` |

Nothing Claude Code reports is stored: the path, version, account and model list are read live, since a stored copy would go stale the moment the user signs out or switches account. Nothing polls.

## The connection

A `provider_connections` row with `auth_kind = 'claude_plan'` (revision `0031`, which rebuilt the table from its stored definition, keeping remote selections aside and putting them back), `provider = 'openai_compatible'`, `base_url = 'https://api.anthropic.com'` and `catalog_provider = 'anthropic'`. It holds no credential: both ciphertext columns stay `NULL`. One per install; it serves `text_gen` only ([`serves.py`](../../surfsense_local/backend/modules/llm/connections/serves.py)), which the agent answers with too. Deleting it deletes the row and forgets `host:platform.claude.com`; Claude Code's sign-in is untouched.

| Route | Does |
|---|---|
| `GET /llm/connections/claude` | `serves` and the `hosts` still to allow. It runs no Claude Code, so a picker shows the row at once |
| `GET /llm/connections/claude/status` | Claude Code's state, read live by running it. Only the dialog asks |
| `POST /llm/connections/claude` | creates the connection: `409` when one exists, `422` with the state when not `ready`, `403 egress_disabled` naming every host still off with `purpose: "claude_plan"` |

Renaming and deleting go through the connection routes; renaming is all a plan allows. The model list is `get_server_info()["models"]`, read live, each listed once by its full id (`resolvedModel`, such as `claude-sonnet-5-5`) so the remote manifest describes its window, images, tool calls and structured output as for any Anthropic model; `default` is dropped. With Claude Code gone since connecting, it answers `409` `claude_sign_in_required`.

## Launching a run

[`launch.py`](../../surfsense_local/backend/modules/llm/subscriptions/claude/launch.py) is the only code that builds `ClaudeAgentOptions`. Callers pass what differs; these they cannot set:

| Option | Value | Why |
|---|---|---|
| `cli_path` | the located binary | the SDK otherwise runs a bundled copy first |
| `setting_sources` | `[]` | the user's `~/.claude` settings, hooks, `CLAUDE.md`, skills and plugins never apply |
| `strict_mcp_config` | `True` | only the MCP servers SurfSense passes |
| `verbatim_prompts` | `True` | `@path` and `/command` in a message are text |
| `permission_mode` | `"default"` | 2.1.301 defaults to `auto`, which approves tools before `can_use_tool` runs |
| `env` | `ANTHROPIC_API_KEY=""`, `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`, the proxy, `NO_PROXY=127.0.0.1,localhost` | a key in the API's environment would replace the plan; no telemetry hosts |

`CLAUDE_CONFIG_DIR` is not set: Claude Code's sign-in lives in the user's own config folder, and a separate one signs out. Errors are read by [`errors.py`](../../surfsense_local/backend/modules/llm/subscriptions/claude/errors.py): `authentication_failed` or a missing binary is `ClaudeSignInRequiredError`, chat kind `claude_sign_in`; a `RateLimitEvent` that is not `allowed` is `ClaudePlanLimitError` with its reset time, kind `claude_limit`; an egress refusal during a reply is `egress_disabled`; any other failed result is `ClaudeRunError`, kind `unknown`. Claude Code sends a `RateLimitEvent` with each reply; one not refused says where the plan stands, `isUsingOverage` meaning its limit is past and extra usage, billed apart from the plan, pays. Chat and Agentic replies pass it on once in a `plan-extra-usage` frame, `{using, resets_at}` ([`extra_usage.py`](../../surfsense_local/backend/modules/llm/subscriptions/claude/extra_usage.py)), and while the last says `using` and a Claude plan model is selected, the composer's notice says "Your plan’s limit is reached, so replies use extra usage until Thu 2:00 PM", before the next message costs extra; it goes when a reply comes back within the plan or at `resets_at`, and gives way to a model issue, which blocks sending ([`extra-usage/`](../../surfsense_local/frontend/src/features/chat/extra-usage/)). Only extra usage off was measured (`overageStatus: rejected`, `org_level_disabled`, `isUsingOverage: false`); the field's meaning when on is the SDK's.

**Packaging.** The SDK's wheels carry Claude Code, 241 MB, in `_bundled/`. `[tool.uv] no-binary-package = ["claude-agent-sdk"]` builds it from source, which carries none; [`test_sdk_install.py`](../../surfsense_local/backend/tests/unit/llm/subscriptions/claude/test_sdk_install.py) fails if `_bundled` holds anything, and the frozen-bundle test fails on any `claude` file. The SDK is pinned exactly.

## Network

Claude Code makes its own HTTPS calls, which no `egress.require()` sees, so every run's `HTTPS_PROXY` is a proxy the API serves on a loopback port from its lifespan. A run refuses to start without one (`ProxyNotServingError`).

| Host | Reached for | Destination |
|---|---|---|
| `api.anthropic.com` | every model call and the model list | `host:api.anthropic.com` |
| `platform.claude.com` | refreshing the sign-in, the binary's `TOKEN_URL` | `host:platform.claude.com` |

- **Chat and status checks** use [`proxy.py`](../../surfsense_local/backend/modules/llm/subscriptions/claude/proxy.py): the two hosts above, each only while allowed, and nothing else ([`proxy_hosts.py`](../../surfsense_local/backend/modules/llm/subscriptions/claude/proxy_hosts.py)).
- **Agent runs** use [`agent_proxy.py`](../../surfsense_local/backend/modules/agent/engines/claude_code/agent_proxy.py): the same two, and the hosts of the ready plugins by the check the plugin proxy applies to opencode ([ADR 0061](../adr/0061-claude-code-reaches-anthropic-and-in-the-agent-the-turns-plugins.md)). A chat run is given no MCP server, so it can never reach a plugin.

Each host is its own row in Settings › Network (the sign-in host labelled "Claude Code sign-in"). Both are asked for in one question ([egress](egress.md)), and every check that admits a Claude plan's call requires both, since with the sign-in host off chat keeps answering until the token expires. A refused tunnel makes Claude Code retry up to ten times as `api_retry`; on the first, the run reads the destinations again and ends with `egress_disabled` when one is off. Each refused host is logged as Claude Code's (`refused Claude Code's CONNECT host:443`).

## Chat

[`chat.py`](../../surfsense_local/backend/modules/llm/subscriptions/claude/chat.py), `ClaudePlanProvider`, implements the `Generator` protocol, so chat, titles and Studio use a Claude plan model as any other, in the API process only ([ADR 0048](../adr/0048-the-api-is-the-only-path-to-a-text-model.md)).

- `tools=[]` ([ADR 0052](../adr/0052-the-chat-model-never-calls-tools.md)) and `max_turns=1`; three with a JSON schema, which maps to `output_format` and comes back as `ResultMessage.structured_output` through Claude Code's own `StructuredOutput` tool. 11 of 11 measured outputs validated.
- SurfSense's system prompt replaces Claude Code's; `--no-session-persistence`; an empty working folder under `<data>/claude/chat`.
- Thinking streams only with `display: "summarized"`; `max_tokens` and `temperature` are dropped, since Claude Code exposes neither.
- **History.** A new or changed conversation is sent as text with the last message after it; the same conversation one message longer sends only the new message to a warm client ([`chat_prompt.py`](../../surfsense_local/backend/modules/llm/subscriptions/claude/chat_prompt.py)). The newest message's images go as image blocks.
- **Warm clients** ([`chat_runs.py`](../../surfsense_local/backend/modules/llm/subscriptions/claude/chat_runs.py)): per conversation, at most four, closed after five minutes idle, never while answering, all closed when the API stops. Measured: 0.9 s to the first token warm, 2.3 s cold.

## Agentic mode

### Two engines

The chat, permission, step and workspace routes reach the agent only through [`AgentEngine`](../../surfsense_local/backend/modules/agent/engines/agent_engine.py), picked by [`thread_engine.py`](../../surfsense_local/backend/modules/agent/engines/thread_engine.py): opencode ([`opencode_engine.py`](../../surfsense_local/backend/modules/agent/engines/opencode_engine.py), today's code unchanged) or Claude Code ([`claude_code/engine.py`](../../surfsense_local/backend/modules/agent/engines/claude_code/engine.py)). A thread records its engine in `chat_threads.agent_engine` (revision `0032`, every earlier agent thread backfilled to `opencode`), and the selected model's connection decides each turn's: `claude_plan` runs on Claude Code. A Claude plan model opens Agentic threads without opencode installed ([`new_chat.py`](../../surfsense_local/backend/modules/llm/capability/modes/new_chat.py)). The tool endpoint, permission answers and step routes are mounted whether or not opencode is, behind the launch key ([agent](agent.md#from-a-thread-to-a-running-opencode)).

### A turn

Prepared as opencode's is: the folder synced, the scope note, sign-ins refreshed, the license checked, changed tools checked, the turn's plugins and rules ([agent](agent.md#plugins)). Then the thread's Claude Code runs it ([`turn.py`](../../surfsense_local/backend/modules/agent/engines/claude_code/turn.py)) with ([`agent_options.py`](../../surfsense_local/backend/modules/agent/engines/claude_code/agent_options.py)):

| Option | Value |
|---|---|
| `cwd` | the thread's folder |
| `tools` | `Read`, `Glob`, `Grep`, `Write`, `Edit`, `Skill`. No Bash ([ADR 0039](../adr/0039-document-scripts-run-without-approval.md)), web, subagents or notebooks |
| `mcp_servers` | a file only the user can read ([`mcp_config.py`](../../surfsense_local/backend/modules/agent/engines/claude_code/mcp_config.py)), removed with the client: `surfsense`, the thread's tool endpoint with the launch key, and each ready plugin with its sign-in header. Given as a dict, the SDK would put the headers on the command line |
| `disallowed_tools` | each given plugin's tools with no rule, so the model is never offered them |
| `plugins`, `skills` | SurfSense's skills as a local plugin, `surfsense`, rebuilt at start with SurfSense's tools named as Claude Code lists them ([`skills_plugin.py`](../../surfsense_local/backend/modules/agent/engines/claude_code/skills_plugin.py)) |
| `system_prompt` | the agent prompt, renamed the same way ([`tool_names.py`](../../surfsense_local/backend/modules/agent/engines/claude_code/tool_names.py)) |
| `hooks`, `can_use_tool` | [the gate](#the-gate) |
| `session_id` or `resume` | the thread's `claude_session_id`, chosen by SurfSense when the thread first needs Claude Code |
| `session_store` | SurfSense's copy of the transcript ([Sessions](#sessions)) |
| `env` | `MCP_TIMEOUT` 25 s, the limit both engines give a plugin to connect; `MCP_TOOL_TIMEOUT` 300 s; `MAX_MCP_OUTPUT_TOKENS` 100,000 |

The user's words go as the last text block of the user message, with SurfSense's notes (handover, scope, mentioned plugins) as blocks before it, and the message's uuid chosen by SurfSense, so the live frames and the thread read back use one id.

**Clients** ([`agent_runs.py`](../../surfsense_local/backend/modules/agent/engines/claude_code/agent_runs.py)). One Claude Code per thread, kept between turns while a digest of its model, thinking switch, servers, hidden tools and skills matches; otherwise it is closed and the session resumed with the new ones. Claude Code lists a server's tools once, when it connects, so a plugin whose offered tools SurfSense recorded otherwise since (a new input schema, say) is connected again with `reconnect_mcp_server`, as opencode's is given again; one that will not reconnect closes the client. Measured: with a schema changed and no reconnect, Claude Code never listed the tools again; `reconnect_mcp_server` returned in 0.07 s with the new schema listed. Closed after five minutes idle, when the thread is deleted, and when the API stops.

**Plugins that cannot be used** ([`plugin_statuses.py`](../../surfsense_local/backend/modules/agent/engines/claude_code/plugin_statuses.py)) are read from the turn's `init` message, which Claude Code holds until each server has connected or failed within `MCP_TIMEOUT`. Asked earlier, every server is `pending`. `failed` or still `pending` is unreachable, `needs-auth` a sign-in or, for SurfSense's own plugins, the license: the same reasons, from the same 25-second limit, as opencode's turn ([agent](agent.md#plugins)). Measured: a plugin taking about 4.5 s was `pending` at 0.6 s and `connected` in `init` at 5.2 s.

**Large results.** A tool result over `MAX_MCP_OUTPUT_TOKENS` is refused; one larger than Claude Code gives whole (an 80.7 KB one was) is saved under `<config home>/projects/<project>/<session id>/tool-results/` with a 2 KB preview and the path, which the gate lets the model read, as opencode's rules leave its tool-output folder open.

### The gate

[`gate.py`](../../surfsense_local/backend/modules/agent/engines/claude_code/gate.py) applies opencode's rules ([`opencode_config.py`](../../surfsense_local/backend/modules/agent/opencode_config.py) and the per-session plugin rules) to Claude Code's tool names. A path is resolved against the thread's folder with links followed before it is compared.

| Tool | Rule |
|---|---|
| `Read`, `Glob`, `Grep` | inside the thread's folder, the skills folder, and this session's saved results ([`saved_results.py`](../../surfsense_local/backend/modules/agent/engines/claude_code/saved_results.py)); nothing else, another session's results and Claude Code's settings included |
| `Write`, `Edit` | under `outputs/` only, never `AGENTS.md`, `CLAUDE.md`, `CONTEXT.md`, `.claude/` or `.opencode/` |
| `Skill` | a `surfsense:` skill only. Claude Code refuses its own skills first: `init` lists 17 of them beside SurfSense's, but measured, the model named only SurfSense's when asked, and a call to `dataviz` with every call allowed was refused as "not in this session's skills allowlist", which `skills` sets. `--disable-slash-commands` was rejected: it removes the Skill tool, SurfSense's skills with it |
| `mcp__surfsense__*` | allowed; each tool refuses for itself what a turn may not do |
| `mcp__<plugin>__<tool>` | the gateway's `allow` or `ask`; any other is refused |
| anything else | refused, with a reason the model reads |

A `PreToolUse` hook decides at once, since a hook has a timeout ([`turn_link.py`](../../surfsense_local/backend/modules/agent/engines/claude_code/turn_link.py)); for `ask`, Claude Code then calls `can_use_tool`, which applies the same rules, sends a `permission-request` frame on the call's step, sets the run to `needs-approval`, and waits for `once` or `reject` from the permission route ([`approvals.py`](../../surfsense_local/backend/modules/agent/engines/claude_code/approvals.py)). Never "always" ([ADR 0028](../adr/0028-model-written-code-runs-with-approval.md)). Measured: an answer 65 s after the ask let the call run; a rejected call never reached the server; in `auto` mode a delete ran without `can_use_tool`, which is why `default` is forced.

### Frames and the thread read back

Claude Code's messages are read as opencode's events ([`opencode_shape.py`](../../surfsense_local/backend/modules/agent/engines/claude_code/opencode_shape.py)) and its transcript as opencode's messages ([`transcript_shape.py`](../../surfsense_local/backend/modules/agent/engines/claude_code/transcript_shape.py)), with tools named and their inputs keyed as opencode's are (`read`, `surfsense_render_document`, `<plugin>_<tool>`, `filePath`). So `TurnFrames`, `step_of`, citations and `thread_turns` serve both engines, and the frontend shows them alike: streamed text, reasoning, steps, approvals, versions made, citations. The reply is stated from what streamed, since the transcript copy lands in batches about 100 ms apart. A compaction's boundary and summary never reach the reply; measured mid-turn, 69,221 tokens became 5,130 and the turn went on.

**Stop** drops every waiting approval, interrupts Claude Code, and reads the interrupted turn to its end within 10 seconds, so its result never answers the next message; past that the client is closed. The reply is recorded `stopped`. **Endings** opencode keeps in its session's metadata are kept for Claude Code in `claude_reply_endings`: `interrupted` from the turn's start, replaced by `stopped` or the error, removed when the reply completes ([`endings.py`](../../surfsense_local/backend/modules/agent/engines/claude_code/endings.py)).

### Sessions

Claude Code writes a session's transcript under `~/.claude/projects/`, which is the user's, not SurfSense's: it deletes transcripts older than `cleanupPeriodDays`, 30 by default, whenever it starts, and the user may clear it or move machines. So [`session_store.py`](../../surfsense_local/backend/modules/agent/engines/claude_code/session_store.py), the SDK's `SessionStore`, copies each line into `claude_session_entries`, each kept once by its uuid. Reading the thread, a step's whole result and Save to Sources read SurfSense's copy; resuming loads it. So Claude Code's transcript is deleted after each turn ([`session_files.py`](../../surfsense_local/backend/modules/agent/engines/claude_code/session_files.py)), and its `<session id>/` folder kept, since a later turn may read a result saved there. Measured: deleted between turns, a running Claude Code went on, writing a new file with only the next turn's lines while the store kept every line, and a relaunch resumed from the store alone. `--no-session-persistence`, which chat runs use, was rejected here: it writes no transcript but mirrors none to the store either, so the next turn found no session. Deleting the thread, or its workspace, closes its Claude Code, deletes SurfSense's copy with the row, and deletes Claude Code's transcript and session folder, whichever engine the thread is on now; a thread that switched engines has its opencode session deleted too. The SDK's `delete_session` is not used, since it stops at a missing transcript and leaves the folder.

A session is resumed only under the Claude account it was made under. `chat_threads.claude_account` keeps a digest of the email and organization `claude auth status` reports, not the email itself; each turn reads it again (0.8 s, measured). Another account signed in since gets the thread a new session, told the whole thread as a [handover](#switching-engines) note, and Claude Code's transcript of the old one is deleted; SurfSense's copy stays, and the thread reads back every session it had. A session made before its account was read is taken as the one signed in now.

### Switching engines

When the selected model moves a thread to the other engine ([`take_over.py`](../../surfsense_local/backend/modules/agent/engines/handover/take_over.py)), the engine taking over resumes its own session, or opens one in the thread's folder, and its turn carries a note of the turns it did not see ([`note.py`](../../surfsense_local/backend/modules/agent/engines/handover/note.py)): each user message, each reply, each tool call with its output cut to 2,000 characters, and the files now in `outputs/`. Reasoning is left out, and so is the old text of a file rewritten since. The note is fitted to 24,000 characters, about 6,000 tokens: older tool outputs go first, then older replies are cut to their first paragraph, then the oldest turns become one line, the newest kept whole. It goes beside the user's words, tagged `<surfsense-handover>`, as opencode's synthetic part or Claude Code's leading block, so each engine's session keeps it and reading the thread leaves it out. A Claude session renewed for another account takes over the same way, with every turn of the thread as the note. Reading a thread merges both sessions' turns by time ([`both_sessions.py`](../../surfsense_local/backend/modules/agent/engines/both_sessions.py)). One engine per thread was rejected: a Claude plan model would be the only one a user could not switch to mid-thread. An engine resumes its own session however often the thread left it: that session holds its own turns whole, tool outputs included, and the note adds the rest, so a fresh session told only the note would know less.

## The dialog

[`claude-option.tsx`](../../surfsense_local/frontend/src/features/models/remote/connections/claude/claude-option.tsx) is the row, [`claude-dialog.tsx`](../../surfsense_local/frontend/src/features/models/remote/connections/claude/claude-dialog.tsx) the nested dialog, one view per state, read live each time it opens and on **Check again**, and [`claude-plan-edit.tsx`](../../surfsense_local/frontend/src/features/models/remote/connections/claude/claude-plan-edit.tsx) the rename-only edit form. **Open install guide** opens `https://code.claude.com/docs/en/setup`, the one page of that site [`external-url.ts`](../../surfsense_local/electron/src/main/external-url.ts) lets through. The egress question for a Claude plan, `purpose: "claude_plan"`, says what each host gets: the API host the prompts and document excerpts, the sign-in host only the sign-in's refresh. Testing a model on a plan says it counts toward the plan's limits. The interface says "Claude plan" and names Claude Code only as the program the user installs ([branding](https://code.claude.com/docs/en/agent-sdk/overview#branding-guidelines)).

## Anthropic's terms

The maintainers own this decision ([ADR 0057](../adr/0057-a-claude-plan-runs-through-the-users-own-claude-code.md)). On 16 Oct 2026, Anthropic's [legal and compliance](https://code.claude.com/docs/en/legal-and-compliance#authentication-and-credential-use) page forbids a third-party Claude.ai login and intermediating its credentials, and does not prevent "an end user from signing in to the unmodified Claude Code binary with their own Claude subscription"; [Use the Claude Agent SDK with your Claude plan](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan) says users can use the SDK and third-party apps with their subscription limits. Anthropic changed this policy four times in 2026 and may enforce it "without prior notice", so removing the feature is deleting the `claude_plan` connection kind and the Claude engine, nothing else.

## Tests

Stand-ins replay what the measured Claude Code sent: a fake `claude` for status ([`claude_stand_in.py`](../../surfsense_local/backend/tests/claude_stand_in.py)), scripted chat runs, and a scripted agent run that meets the turn's own hook and `can_use_tool` and mirrors its transcript ([`claude_agent_stand_in.py`](../../surfsense_local/backend/tests/claude_agent_stand_in.py)). [`test_both_engines.py`](../../surfsense_local/backend/tests/integration/agent/claude_code/test_both_engines.py) runs the same scenarios through opencode and the stand-in (an answer, a write allowed and one refused, a plugin call approved, Stop) and compares what the chat shows and reads back, ids, step titles and tool outputs aside. Tests under the `claude_code` marker run the developer's own Claude Code on their plan, opted into with `SURFSENSE_CLAUDE_CODE_TESTS=1`; CI never selects them. Every run reads the installed version, and one newer than `NEWEST_TESTED`, `2.1.301`, is named once in the log as possibly breaking what this page measured ([`tested_version.py`](../../surfsense_local/backend/modules/llm/subscriptions/claude/tested_version.py)). `NEWEST_TESTED` is raised only once the `claude_code` tests pass on the newer Claude Code; all 18 passed on `2.1.301` on 17 Oct 2026.

## Known gaps

- Windows and Linux are untested on a real install: whether `claude auth status` prints the same JSON, whether `HTTPS_PROXY` is honoured the same way, and WinGet's `Links` folder.
- The Claude engine does not refuse a Claude Code below `MIN_VERSION` before a turn, as the dialog does; it runs whatever binary it finds.
- A Claude Code update that changes what this page measured is caught only when someone runs the `claude_code` tests on it; until then, only the log warning says it is untested.
- The extra-usage notice is built on the SDK's description of `isUsingOverage`; no plan using extra usage was at hand to measure it.
