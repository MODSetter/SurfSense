# The dialog

> **Use your Claude plan** sits beside **Use your ChatGPT plan** in Settings › Add model and in onboarding's model step. Clicking it opens a nested dialog that explains the feature and walks the user to a ready connection. SurfSense cannot sign the user in, so the dialog's job is to say what Claude Code needs and to check it again on request.

Part of [Use your Claude plan](README.md).

## Where it lives

`frontend/src/features/models/remote/connections/claude/`, a sibling of [`chatgpt/`](../../../surfsense_local/frontend/src/features/models/remote/connections/chatgpt/):

| File | Does |
|---|---|
| `claude-option.tsx` | the row: title, one-line body, and once connected "Connected as … · Max plan" with **Show models** |
| `claude-dialog.tsx` | the nested dialog, one view per state |
| `use-claude-status.ts` | reads `GET /llm/connections/claude`; **Check again** posts `…/check` |
| `api.ts` | the three routes ([`01-connection.md`](01-connection.md#routes)) |

The row is mounted where the ChatGPT row is: [`add-model-options.tsx`](../../../surfsense_local/frontend/src/features/models/add-model/add-model-options.tsx) and [`model-step.tsx`](../../../surfsense_local/frontend/src/features/onboarding/model-step/model-step.tsx). The dialog uses the app's dialog component, nested in the open one, and the shared button; every string is a message, translated like the ChatGPT row's.

## The views

The dialog opens on the status read when it opens. Every view has the same opening lines: SurfSense uses the user's Claude Pro, Max or Team plan through Claude Code on this computer; the sign-in stays in Claude Code and SurfSense never sees it; usage counts toward the plan, the same limits as Claude Code.

| State | The dialog shows | Actions |
|---|---|---|
| `not_installed` | Step 1, install Claude Code; step 2, open a terminal, run `claude` and sign in | **Open install guide**, **Check again**, **Cancel** |
| `signed_out` | Claude Code is installed but not signed in; run `claude` in a terminal and sign in | **Check again**, **Cancel** |
| `too_old` | the version found and the lowest accepted | **Open update guide**, **Check again**, **Cancel** |
| `ready` | "Connected as <email> · <plan>", where Claude Code was found and its version, and that Claude models work in chat and in the agent | **Add Claude models**, **Cancel** |

**Check again** reads the status and moves to the view it returns. Nothing polls: nothing changes on SurfSense's side until the user acts in their terminal.

**Add Claude models** posts the connection. Refused with `egress_disabled`, it raises the usual egress prompt for `api.anthropic.com` nested over the dialog ([egress](../../architecture/egress.md#asking-for-consent)), and posts again on Allow. On success the dialog closes and the models appear in every picker.

**Opened again** once connected, the dialog shows the `ready` view with **Remove** in place of **Add Claude models**, or the state that now applies, such as `signed_out` after the user signed out in Claude Code.

## Names

The interface says "Claude plan" and "Use your Claude plan", and names Claude Code only as the program the user installs and signs in to. SurfSense's own feature is never called "Claude Code" ([branding](https://code.claude.com/docs/en/agent-sdk/overview#branding-guidelines)).
