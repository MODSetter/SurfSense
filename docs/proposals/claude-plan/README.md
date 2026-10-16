---
status: proposed
code:
  - surfsense_local/backend/modules/llm/subscriptions/claude/
  - surfsense_local/backend/modules/llm/connections/
  - surfsense_local/backend/modules/llm/models.py
  - surfsense_local/backend/modules/agent/engines/
  - surfsense_local/backend/modules/agent/agent_threads/
  - surfsense_local/backend/modules/agent/plugin_proxy/
  - surfsense_local/backend/modules/chat/
  - surfsense_local/backend/alembic/versions/
  - surfsense_local/backend/bundling/api.spec
  - surfsense_local/backend/pyproject.toml
  - surfsense_local/frontend/src/features/models/remote/connections/claude/
  - surfsense_local/frontend/src/features/models/add-model/
  - surfsense_local/frontend/src/features/onboarding/model-step/
---

# Use your Claude plan

> A Claude Pro, Max or Team subscriber picks **Use your Claude plan** and gets Claude's models in chat and in the agent, paid for by their plan. SurfSense never signs in to Claude and never holds a Claude credential: it drives the user's own installed, unmodified Claude Code through Anthropic's [Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview), and Claude Code keeps the sign-in. SurfSense ships no copy of Claude Code. Chat runs Claude Code with every tool off. The agent runs it as a second engine beside opencode, with SurfSense's tools over MCP and SurfSense's permission rules enforced in a `PreToolUse` hook.

This reverses one line of [ADR 0038](../../adr/0038-chatgpt-plans-sign-in-through-openai-not-codex.md), "A Claude subscription is not offered; Claude stays reachable with an API key", and adds an exception to [ADR 0050](../../adr/0050-a-model-answers-on-its-own-route-with-its-connections-credential.md), "SurfSense owns a plan's sign-in". Both get a superseding ADR with this proposal's acceptance ([Decisions](#decisions-this-records)). The ChatGPT plan it sits beside is in [ChatGPT subscription](../../architecture/chatgpt-subscription.md).

Every behaviour of Claude Code stated here was measured on 16 Oct 2026 on macOS arm64, against Claude Code `2.1.301` (native installer) signed in to a Max plan, with the Python `claude-agent-sdk` `0.2.168` ([Measurements](#measurements)). Windows and Linux are untested and listed under [Open questions](#open-questions).

## Parts

| Part | File | Owns |
|---|---|---|
| **Connection** | [`01-connection.md`](01-connection.md) | finding Claude Code, its status, the `claude_plan` connection, how every run is launched, network, errors, packaging |
| **Chat** | [`02-chat.md`](02-chat.md) | a `Generator` over Claude Code with no tools |
| **Agent** | [`03-agent.md`](03-agent.md) | an engine interface, the Claude engine, the permission gate, frames, sessions |
| **Handover** | [`04-handover.md`](04-handover.md) | switching an agent thread between a Claude plan model and any other |
| **Dialog** | [`05-dialog.md`](05-dialog.md) | the nested dialog behind **Use your Claude plan** |

## What changes

| | Today | With this |
|---|---|---|
| Claude in SurfSense | an Anthropic API key connection only | also a `claude_plan` connection, billed to the user's plan |
| Credential SurfSense holds for it | the API key | none |
| Claude Code | never run | the user's own install, found on disk, run per conversation; never shipped, downloaded or updated by SurfSense |
| Chat engine | providers over HTTP | adds `ClaudePlanProvider`, Claude Code with `tools=[]` |
| Agent engines | opencode | opencode, and Claude Code for a thread on a Claude plan model |
| Engine choice | a thread is the agent's or the chat's | an agent thread also records which engine runs it, set by the selected model's connection |
| Model switch in an agent thread | opencode carries the session | the same, unless the switch crosses engines: then a handover note |
| Network | `host:api.anthropic.com` for a key connection | the same destination; Claude Code reaches it only through SurfSense's proxy |
| Installer | unchanged | unchanged: the SDK's bundled Claude Code (241 MB) is excluded |

## How the user sees it

1. In **Settings › Add model** or onboarding's model step, the user picks **Use your Claude plan**. A nested dialog opens ([`05-dialog.md`](05-dialog.md)).
2. The dialog shows what SurfSense found: Claude Code not installed, too old, signed out, or ready with the account's email and plan. Each state says the one thing to do, and **Check again** re-reads it. Signing in happens in the user's terminal, in Claude Code.
3. **Add Claude models** asks for `api.anthropic.com` through the usual egress prompt, closes the dialog, and lists Claude Code's models in every picker.
4. A Claude plan model then works in Basic and Agentic threads like any other model. The user never picks an engine.
5. A used-up plan, a signed-out Claude Code or a missing install shows the existing `subscription_limit` and `subscription_sign_in` notices, or the connection's not-found state.

## Decisions this records

| Decision | Choice |
|---|---|
| How SurfSense reaches a Claude plan | Through the user's installed Claude Code, via the Agent SDK. No OAuth client, token, `setup-token` or Keychain read of SurfSense's own. |
| Bundling | None. The SDK's `_bundled/claude` is excluded from the build, and every run names the user's binary in `cli_path` ([`01-connection.md`](01-connection.md#packaging)). |
| Where the sign-in lives | In Claude Code, in the user's own `~/.claude`. A separate `CLAUDE_CONFIG_DIR` loses it ([Measurements](#measurements)). |
| Chat | Claude Code with `tools=[]` and one turn, behind the `Generator` protocol. [ADR 0052](../../adr/0052-the-chat-model-never-calls-tools.md) holds. |
| Agent | A second engine beside opencode, behind a new engine interface. Claude Code's file tools on the thread folder; SurfSense's tools and the thread's plugins over MCP; Bash, web and subagents off. |
| Permissions | SurfSense's rules decide every tool call in a `PreToolUse` hook, with `can_use_tool` as a second gate and `permission_mode="default"` forced, since Claude Code 2.1.301 defaults to `auto` and then skips `can_use_tool` ([`03-agent.md`](03-agent.md#the-gate)). |
| Switching models mid-thread | Allowed. Crossing engines writes a handover note ([`04-handover.md`](04-handover.md)). One engine per thread was rejected. |
| Network | Claude Code's `HTTPS_PROXY` is SurfSense's proxy, which tunnels `api.anthropic.com` only, after `egress.require()`. Non-essential traffic is off. |
| Name | "Claude plan" and "Use your Claude plan". Never "Claude Code" in the interface ([branding](https://code.claude.com/docs/en/agent-sdk/overview#branding-guidelines)). |

The superseding ADR records: a Claude plan is offered through the user's own Claude Code and SurfSense holds no Claude credential, replacing ADR 0038's last consequence; and ADR 0050's "SurfSense owns a plan's sign-in for both engines" holds for the ChatGPT plan only.

## Anthropic's terms

The maintainers own this decision. What the sources say on 16 Oct 2026:

- **Against a SurfSense sign-in.** [Legal and compliance](https://code.claude.com/docs/en/legal-and-compliance#authentication-and-credential-use): "Anthropic does not permit third-party developers to offer Claude.ai login into their own applications, or to route requests through Free, Pro, or Max plan credentials on behalf of their users", and developers "may not collect, store, or intermediate Claude.ai credentials or session tokens". The [Agent SDK overview](https://code.claude.com/docs/en/agent-sdk/overview): "Unless previously approved, Anthropic does not allow third party developers to offer claude.ai login or rate limits for their products, including agents built on the Claude Agent SDK."
- **For the user's own Claude Code.** The same legal page does not prevent "an end user from signing in to the unmodified Claude Code binary with their own Claude subscription". [Use the Claude Agent SDK with your Claude plan](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan), updated 7 Oct 2026: users "can still use the Claude Agent SDK, `claude -p`, and third-party apps with your subscription limits".
- **Shipping Claude Code** in a product requires the Commercial Terms and an unmodified binary ([legal and compliance](https://code.claude.com/docs/en/legal-and-compliance#can-customers-offer-claude-code-in-their-products)). This proposal ships none.
- **Precedent.** [OpenClaw](https://docs.openclaw.ai/providers/anthropic) runs the user's installed Claude Code and "never reads, persists, refreshes, selects, or forwards the native login tokens"; this design follows it. opencode removed its own Claude sign-in "per legal requests" ([anomalyco/opencode#18186](https://github.com/anomalyco/opencode/pull/18186), merged 19 Mar 2026). Hermes Agent reads Claude Code's credentials and calls the API itself, and its docs say that path draws only on extra-usage credits, not the plan ([Hermes providers](https://hermes-agent.nousresearch.com/docs/integrations/providers)).

Anthropic changed this policy in January, February, April and June 2026, and may enforce "without prior notice". The feature is built so that removing it is deleting the `claude_plan` connection kind and the Claude engine, nothing else.

## Build order

1. This proposal and the superseding ADR.
2. **Connection and chat**: [`01-connection.md`](01-connection.md), [`02-chat.md`](02-chat.md), [`05-dialog.md`](05-dialog.md). A Claude plan serves `text_gen` only until step 4.
3. **The engine interface**, with opencode moved behind it and no change in behaviour ([`03-agent.md`](03-agent.md#the-engine-interface)).
4. **The Claude engine and the handover** ([`03-agent.md`](03-agent.md), [`04-handover.md`](04-handover.md)); `serves` gains the agent.
5. Windows and Linux: install locations and the proxy.

## Measurements

Scripts kept out of the repo; each line is one run on the machine above.

| What | Result |
|---|---|
| Finding `claude` with a GUI app's PATH (`/usr/bin:/bin:/usr/sbin:/sbin`) | not on PATH; found at `~/.local/bin/claude`, the native installer's link |
| `claude auth status` | JSON: `loggedIn`, `authMethod: "claude.ai"`, `email`, `subscriptionType: "max"`; with an empty `CLAUDE_CONFIG_DIR`, `loggedIn: false` |
| `ANTHROPIC_API_KEY` set in the environment | Claude Code uses it in place of the plan, and its init message names that variable as the key's source |
| Separate `CLAUDE_CONFIG_DIR` | first request fails `authentication_failed` |
| `--no-session-persistence` | no transcript written under `~/.claude/projects` |
| `get_server_info()["models"]` | `default`, `opus`, `claude-fable-5-1[1m]`, `sonnet`, `haiku`, each with `displayName`, `resolvedModel`, effort levels |
| Chat, `tools=[]`, own `system_prompt` | init reports `tools: []`; the model follows SurfSense's prompt; 652 tokens cached on the first request |
| Latency (haiku) | connect 1.0 s; first token 2.3 s cold, 0.9 s on a running client; history-as-text turn 1.4 s |
| Three conversations at once | 1.7 s wall |
| Thinking | streams `thinking_delta` only with `display: "summarized"` |
| Signed out | `AssistantMessage.error == "authentication_failed"` within 0.04 s |
| Plan usage | `RateLimitEvent`: `status`, `resetsAt`, five-hour and seven-day utilisation |
| HTTP MCP with an `Authorization` header | connected; every call carried the key |
| Default permission mode | `auto` on 2.1.301 (the VS Code extension's 2.1.300 ran `default`); `can_use_tool` never called and a delete ran unapproved |
| `permission_mode="default"` | `can_use_tool` asked; delete refused |
| Waiting `PreToolUse` hook, mode left `auto` | delete refused, on haiku and sonnet |
| File tools confined by the hook | read `sources/` and write `outputs/` allowed; writes to `../` and `/tmp` refused; a `CLAUDE.md` in the folder not loaded |
| `interrupt()` | returns in 0.01 s; the turn ends `error_during_execution`; the client takes the next query |
| Resume by session id in a new client | remembers the earlier turn |
| Resume from a `SessionStore` after deleting the local transcript | works; with `--no-session-persistence` it does not |
| Proxy tunnelling only `api.anthropic.com` | works; with non-essential traffic off, nothing else is attempted (without it, `http-intake.logs.us5.datadoghq.com`) |
| Proxy refusing `api.anthropic.com` | no error: `system` `api_retry` messages, first after about 1 s, up to 10 attempts |

## Out of scope

A SurfSense sign-in to Claude, reading or storing Claude Code's credentials, `claude setup-token`, shipping or downloading Claude Code, Claude Code's own Bash, web tools, subagents or skills in the agent, and the API credits Max and Team plans include, which already work through an API key connection ([API credits](https://platform.claude.com/docs/en/about-claude/api-credits-for-subscribers)).

## Open questions

- Windows and Linux: where installers put `claude`, whether `HTTPS_PROXY` is honoured the same way, and `claude.exe` versus npm's `claude.cmd` shim.
- The lowest Claude Code version to accept, and how often a contract test against the real binary runs.
- Whether a plan limit reached with Claude Code's extra usage switched on should say so; `overageStatus` is in the `RateLimitEvent`.
- Whether transcripts the agent engine writes under `~/.claude/projects` should be deleted once mirrored ([`03-agent.md`](03-agent.md#sessions)).
