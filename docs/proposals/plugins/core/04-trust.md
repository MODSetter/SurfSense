# Trust

> Owns: approval and per-tool permissions in the gateway, the approval dialog's plugin variant, the activity view, organisation policy hooks.
> Related: [`02-registry.md`](02-registry.md) (review, allowing third-party plugins, tools added later), [`../remote/README.md`](../remote/README.md) (credentials, egress).

## What a remote plugin can and cannot do

| It can | It cannot |
|---|---|
| Offer tools, with descriptions, schemas and annotations | See the user's files, Sources, workspace or conversation. It gets only the arguments of a call |
| Return text, images and structured data into the turn | Save into Sources. The user does, with Save to Sources |
| Ask the user to sign in, or for a key | Run anything on the user's machine |
| Report progress on a long call | Make the app contact any host but its declared ones |
| Change its server whenever its publisher deploys | Get a tool called that the user has not switched on, or skip approval |

What leaves the machine is each call's arguments, sent to the plugin's host. That is the trade a plugin makes, and the screen says so before Connect: the publisher, the hosts and the privacy policy.

## Approval

The gateway decides whether a call must be approved, from the tool's MCP annotations and the user's setting for it. A server that sets no annotations gets MCP's defaults: not read-only, possibly destructive, open world.

| Tool | Before a call |
|---|---|
| `readOnlyHint: true` on a plugin from the first-party list | Runs without asking. Annotations are the server's own claim, trusted only from servers SurfSense runs |
| Not destructive | Asks, offering Allow once or Deny, until the user sets the tool to Always allow in Settings → Plugins. A third party's read-only tool is here too |
| `destructiveHint: true` | Asks every call, offering Allow once or Deny; Always allow does not apply to it |

This follows Claude's connectors, where a new tool needs approval until the user allows it always, and only a tool annotated read-only skips it.

- In an agent thread, opencode asks. Each turn, SurfSense gives opencode a rule per plugin tool with its server, `allow`, `ask` or `deny` as the gateway decided, every unreviewed tool denied ([`03-engines.md`](03-engines.md#each-turn)), so a plugin call is asked about through the agent's own permission prompt: opencode's request, the turn's `permission-request` frame, the agent's approval dialog ([`approval-dialog.tsx`](../../../../surfsense_local/frontend/src/features/agent/approval-dialog.tsx)) with the plugin, its publisher badge, the tool's title and the exact arguments, and the thread's permission route back to opencode.
- The prompt offers Allow once or Deny, never "always": SurfSense does not answer the agent with "always" ([ADR 0028](../../../adr/0028-model-written-code-runs-with-approval.md)). Always allow is a setting of the tool, stored as `plugin_tools.approval` (`always`, otherwise `ask`), set and revoked in Settings → Plugins, and it reaches opencode as `allow` at the next turn.
- An `@` mention asks as any call does: the agent chose the inputs, not the user ([`03-engines.md`](03-engines.md#-mentions)).
- A call not answered before its deadline ends `denied`, and the model is told the user did not answer.

## Permissions per tool

Settings → Plugins shows each connected plugin's tools in two groups, read-only and the rest, each tool with an on/off switch and its approval setting, and each group with one setting for all its tools, as browser extensions show their permissions. A new tool starts off ([`02-registry.md`](02-registry.md#tools-added-later)). Each plugin has an activity view: its recent calls, from which thread, with what arguments, and how they ended.

## Prompt injection

The user's sources, and a plugin's own results, can carry text aimed at the model, and a tool description from a server is text the model reads too. A source can steer the model into calling a tool and sending what it read to that tool's host.

- Approval with the exact arguments is the main defence.
- Hosts are declared and consented, so data can go only to a host the user allowed. For the agent the check runs as each turn is given its plugins.
- Tool descriptions are reviewed when an entry is listed and shown on the plugin's row, and a changed description switches the tool off until the user allows it again ([`02-registry.md`](02-registry.md#tools-added-later)); for the agent the switch is a `deny` rule, so a changed tool is refused, and its new text reaches the model only if opencode cannot leave a blocked tool out of what it lists ([`03-engines.md`](03-engines.md#each-turn), [open questions](../README.md#open-questions)). Where SurfSense itself lists tools to a model, as the chat engine will, it cuts each description to 2,000 characters; opencode reads descriptions from the server, so the agent's are not cut.
- Third-party plugins stay off until the user allows them, so they never reach a user who did not choose them.

None of this is a sandbox.

## Organisation policy

Later Enterprise work, kept possible by this design: a policy can turn plugins off, keep third-party plugins off, or allow a fixed list of plugin ids. The gateway is the one place that would read it.

## Acceptance

- A tool asks until it is set to Always allow in Settings → Plugins, and from the next turn does not; revoking it restores the prompt.
- A destructive tool asks on every call, even set to Always allow, and after an `@` mention.
- The prompt offers Allow once and Deny only.
- A tool with no annotations asks on every call.
- A read-only tool runs without asking on a first-party plugin, and asks on a third-party one.
- A call left unanswered past its deadline ends `denied`.
- The activity view lists a call's thread, arguments and outcome, and no credential.
