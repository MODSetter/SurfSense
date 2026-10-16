# ADR 0057: A Claude plan is reached through the user's own Claude Code, and SurfSense holds no Claude credential

- **Status:** Accepted; its network decision superseded by [ADR 0059](0059-claude-code-reaches-anthropic-and-in-the-agent-the-turns-plugins.md)
- **Date:** 2026-10-16
- **Supersedes:** [ADR 0038](0038-chatgpt-plans-sign-in-through-openai-not-codex.md) in part: its consequence that a Claude subscription is not offered. [ADR 0050](0050-a-model-answers-on-its-own-route-with-its-connections-credential.md) in part: that SurfSense owns a plan's sign-in for both engines, which now holds for the ChatGPT plan only
- **Source:** [Use your Claude plan proposal, decisions and Anthropic's terms L59–84](https://github.com/MODSetter/SurfSense/blob/e1332966dd2ec2cfcf636331da6f770d836fcff1/docs/proposals/claude-plan/README.md#L59-L84)

## Context

ADR 0038 left Claude reachable only with an API key, because Anthropic forbids a third-party app to sign users in to Claude. That still holds: "Anthropic does not permit third-party developers to offer Claude.ai login into their own applications", and developers "may not collect, store, or intermediate Claude.ai credentials or session tokens" ([legal and compliance](https://code.claude.com/docs/en/legal-and-compliance#authentication-and-credential-use)). opencode removed its own Claude sign-in "per legal requests" ([anomalyco/opencode#18186](https://github.com/anomalyco/opencode/pull/18186)), and Hermes Agent, which calls the API with Claude Code's credentials, draws only on extra-usage credits, not the plan ([Hermes providers](https://hermes-agent.nousresearch.com/docs/integrations/providers)).

The same terms do not prevent "an end user from signing in to the unmodified Claude Code binary with their own Claude subscription", and Anthropic's support page, updated 7 Oct 2026, says the Agent SDK and third-party apps can use a plan's limits ([support](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan)). OpenClaw runs the user's installed Claude Code this way and never touches its tokens ([OpenClaw](https://docs.openclaw.ai/providers/anthropic)).

A Claude plan has no HTTP endpoint SurfSense may call, so opencode cannot reach it through the model endpoint as it reaches a ChatGPT plan (ADR 0050): Claude Code runs its own agent loop.

## Decision

- A Claude plan is offered as a `claude_plan` connection that drives the user's own installed, unmodified Claude Code through Anthropic's Agent SDK. Claude Code keeps the sign-in, in the user's own config directory. SurfSense runs no sign-in flow, stores no Claude credential, never reads Claude Code's, and never uses `claude setup-token`.
- SurfSense ships, downloads and updates no Claude Code. The SDK's bundled copy is excluded from the build, and every run names the user's binary in `cli_path`.
- Chat runs Claude Code with no tools and one turn, behind the `Generator` protocol, so [ADR 0052](0052-the-chat-model-never-calls-tools.md) holds.
- The agent runs Claude Code as a second engine beside opencode, behind an engine interface, with SurfSense's tools and plugins over MCP and Claude Code's file tools confined to the thread folder. SurfSense's permission rules decide every tool call in a `PreToolUse` hook, with `can_use_tool` as a second gate and `permission_mode="default"` forced.
- Claude Code's network traffic goes through SurfSense's proxy, which tunnels only `api.anthropic.com` once the user allows it ([ADR 0027](0027-egress-consent-per-host.md)).
- The feature is called "Claude plan" and never "Claude Code".

## Consequences

- Claude Pro, Max and Team subscribers use their plan in chat and in the agent. The user must install Claude Code and sign in to it themselves; SurfSense can only say how.
- Usage shares the plan's limits with the user's own Claude Code use.
- The agent gains a second engine to maintain. A thread that switches models across engines carries a handover note, and each engine keeps its own session.
- SurfSense depends on a binary it does not control and that updates itself. Claude Code 2.1.301 already changed its default permission mode to `auto`, which skips `can_use_tool`; the forced mode, the hook and a contract test against the real binary cover that kind of change.
- Anthropic has changed this policy several times in 2026 and may enforce "without prior notice". Withdrawing the feature is removing the `claude_plan` connection kind and the Claude engine; nothing else depends on them.
- The API key connection stays, and Max and Team plans' monthly API credits keep working through it.

## Where the code stands

Not built. The work is laid out in the [Use your Claude plan](../proposals/claude-plan/README.md) proposal.
