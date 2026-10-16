# The dialog

> **Use your Claude plan** sits beside **Use your ChatGPT plan** in Settings › Add model and in onboarding's model step. Clicking it opens a nested dialog that explains the feature and walks the user to a ready connection. SurfSense cannot sign the user in, so the dialog's job is to say what Claude Code needs and to check it again on request.

Part of [Use your Claude plan](README.md).

## Where it lives

`frontend/src/features/models/remote/connections/claude/`, a sibling of [`chatgpt/`](../../../surfsense_local/frontend/src/features/models/remote/connections/chatgpt/):

| File | Does |
|---|---|
| `claude-option.tsx` | the row: the Claude icon, title and one-line body; **Set up** opens the dialog, or once connected "Connected through Claude Code on this computer" with **Show models** |
| `claude-dialog.tsx` | the nested dialog, one view per state, read live each time it opens |
| `claude-plan-edit.tsx` | the connection form for a Claude plan: rename only, no URL, key or sign-in |
| `api.ts` | `GET /llm/connections/claude`, and connecting after one egress question for every host still off |

The row is mounted where the ChatGPT row is: [`add-model-options.tsx`](../../../surfsense_local/frontend/src/features/models/add-model/add-model-options.tsx) and [`model-step.tsx`](../../../surfsense_local/frontend/src/features/onboarding/model-step/model-step.tsx). The dialog uses the app's dialog component, nested in the open one, and the shared button; every string is a message, translated into every language in `LOCALES`.

## The views

Every view opens with the same lines: SurfSense uses the user's Claude Pro, Max or Team plan through Claude Code on this computer; the sign-in stays in Claude Code and SurfSense never sees it; use counts toward the plan's limits, as it does in Claude Code.

| State | The dialog shows | Actions |
|---|---|---|
| `not_installed` | step 1, install Claude Code; step 2, open a terminal, run `claude` and sign in | **Open install guide**, **Check again**, **Cancel** |
| `signed_out` | Claude Code is installed but not signed in to a plan; run `claude` in a terminal and sign in | **Check again**, **Cancel** |
| `too_old` | the version found, to update; or, when no version could be read, that SurfSense could not tell | **Check again**, **Cancel** |
| `ready` | "Connected as <email>, <plan>", and that Claude models then work in chat, titles and Studio | **Add Claude models**, **Cancel** |

**Check again** reads the status again and moves to the view it returns. Nothing polls: nothing changes on SurfSense's side until the user acts in their terminal.

**Open install guide** opens Anthropic's guide, `https://code.claude.com/docs/en/setup`, the one page on that site Electron's link allowlist lets through ([`external-url.ts`](../../../surfsense_local/electron/src/main/external-url.ts)).

**Add Claude models** first asks about every host still off, `api.anthropic.com` for chats and `platform.claude.com` for the sign-in's refresh ([`01-connection.md`](01-connection.md#network)), in one egress prompt nested over the dialog ([egress](../../architecture/egress.md#asking-for-consent)), then posts the connection. Allow switches each host on as its own row; Cancel creates nothing and the dialog says which host is needed. On success the dialog closes and the models appear in every picker.

The egress prompt asks about several hosts in one question: a refusal's `hosts` and an `askEgress` call's `also` are named in it, and Allow switches each on. A Claude plan's question, `purpose: "claude_plan"`, says what each host gets: the API host what the model is sent, chats and sources; the sign-in host only the sign-in's refresh, and that turning it off stops Claude once the sign-in expires. Other questions naming several hosts, a ChatGPT sign-in's two and a plugin's, add "Allowing also lets SurfSense reach …". In Settings › Network the sign-in host's row is labelled "Claude Code sign-in".

**Editing** a Claude plan from the connection list opens `claude-plan-edit.tsx`: the name is editable, the provider is shown fixed as "Claude plan", and it says that signing in, out or switching accounts happens with `claude` in a terminal. Removing it is the connection list's own delete, as for any connection.

**When chat fails** on a Claude plan, it says so in Claude's terms, not ChatGPT's: `claude_sign_in` asks to run `claude` and sign in, `claude_limit` says the Claude plan's limit is reached, and the model check's `claude_sign_in_required` says Claude Code is missing or signed out.

## Names

The interface says "Claude plan" and "Use your Claude plan", and names Claude Code only as the program the user installs and signs in to. SurfSense's own feature is never called "Claude Code" ([branding](https://code.claude.com/docs/en/agent-sdk/overview#branding-guidelines)).
