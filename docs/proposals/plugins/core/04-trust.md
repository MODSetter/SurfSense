# Trust

> Owns: approval and per-tool permissions in the gateway, the approval dialog's plugin variant, the activity view, organisation policy hooks.
> Related: [`02-registry.md`](02-registry.md) (review, Restricted mode, tools added later), [`../remote/README.md`](../remote/README.md) (credentials, egress).

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

Approval follows the tool's MCP annotations. A server that sets none gets MCP's defaults: not read-only, possibly destructive, open world.

| Tool | Before a call |
|---|---|
| `readOnlyHint: true` | Asks on the tool's first call, offering Allow once, Always allow this tool, or Deny |
| Not read-only, not destructive | Asks every call, offering the same three |
| `destructiveHint: true` | Asks every call, offering Allow once or Deny |

- The dialog shows the plugin, its publisher badge, the tool's title, and the exact arguments.
- It is the agent's existing approval dialog ([`approval-dialog.tsx`](../../../../surfsense_local/frontend/src/features/agent/approval-dialog.tsx)) with a plugin variant. In both kinds of thread, the run goes `needs-approval` while it waits, and the answer goes to `POST /chat/threads/{id}/permissions/{request_id}`, which today serves opencode's own requests; plugin requests are answered by the gateway rather than passed to opencode.
- "Always allow" is stored per tool in `plugin_tools.approval` and can be changed or revoked in Settings → Plugins.
- An `@` mention approves its own call, except for a destructive tool ([`03-engines.md`](03-engines.md#-mentions)).
- A call not answered before its deadline ends `denied`, and the model is told the user did not answer.

## Permissions per tool

Settings → Plugins shows each connected plugin's tools with an on/off switch and its approval setting, as browser extensions show their permissions. A new tool starts off ([`02-registry.md`](02-registry.md#tools-added-later)). Each plugin has an activity view: its recent calls, from which thread, with what arguments, and how they ended.

## Prompt injection

The user's sources, and a plugin's own results, can carry text aimed at the model, and a tool description from a server is text the model reads too. A source can steer the model into calling a tool and sending what it read to that tool's host.

- Approval with the exact arguments is the main defence. It is why a tool that is not read-only asks every time.
- Hosts are declared and consented, so data can go only to a host the user allowed.
- Tool descriptions are reviewed when an entry is listed, capped at 2,000 characters, and shown to the user on the plugin's row. A description that changes after connecting switches the tool off as a new one would.
- Restricted mode keeps third-party plugins away from users who never chose them.

None of this is a sandbox, and the docs say so. It is the same position Obsidian takes on its community plugins.

## Organisation policy

Later Enterprise work, kept possible by this design: a policy can turn plugins off, keep Restricted mode on, or allow a fixed list of plugin ids. The gateway is the one place that would read it.

## Acceptance

- A read-only tool asks on its first call and not again after Always allow; switching it back to ask restores the dialog.
- A destructive tool asks on every call and never offers Always allow, including after an `@` mention.
- A tool with no annotations asks on every call.
- A call left unanswered past its deadline ends `denied`.
- A tool whose description changes after connecting is switched off and listed as changed.
- The activity view lists a call's thread, arguments and outcome, and no credential.
