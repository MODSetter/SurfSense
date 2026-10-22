# Migration and rollout

## Existing threads

2.x uses the same `opencode.db` under its data folder and imports 1.x's sessions into it on first start, in place, in under a second for a few sessions ([`core/src/database/v1-migration.bun.ts`](https://github.com/anomalyco/opencode/blob/v2.1.2/packages/core/src/database/v1-migration.bun.ts)); progress is at `GET /api/experimental/migration/v1`. Measured on macOS and Windows:

- Session ids, titles, folders and metadata are kept, so `chat_threads.opencode_session_id` stays valid and endings recorded on a session survive.
- A session's permission rules are dropped; the backend sends them again before the session's next turn.
- Old tool items keep 1.x's names and inputs (`write`, `filePath`); 2.x adds a note to the model that `read` and `write` now take `path`. The readers and the step labels in [`step-label.tsx`](../../../surfsense_local/frontend/src/features/agent/step-label.tsx) take both spellings.
- An old compaction becomes a `compaction` message; a new prompt on an old session works.
- 1.x can still read the database afterwards, so going back a release keeps every thread made before the update.
- The import runs once. A 1.x turn written after it never appears in 2.x, so the app stops 1.x before 2.x's first start, which an update does by replacing the binary.

## What must not regress

Each of these breaks if the move is made without it, and each was shown to hold with it:

| Without | Breaks | Held by |
|---|---|---|
| `codemode: false`, `execute` denied | tool outputs, approvals, network isolation | [tool calls](04-tool-calls.md) |
| edit rules relative to the folder | the agent cannot write `outputs/` | [permissions](03-config-and-permissions.md#permissions) |
| `external_directory` denied explicitly | reads outside the thread folder | [permissions](03-config-and-permissions.md#permissions) |
| reading the configuration back | one bad value silently removes the agent | [verification](03-config-and-permissions.md#verification) |
| `buffer` and `keep.tokens` set | compaction too late on 32k windows | [keys](03-config-and-permissions.md#keys) |
| the plugins minus-list | loopback probes, opencode's own skills and `execute` hint | [keys](03-config-and-permissions.md#keys) |
| waiting for `connected` | a first turn without its MCP tools | [plugins](05-plugins.md#registration) |
| `x-should-retry: false` | endless retries of SurfSense's own 409s | [model endpoint](06-model-endpoint.md) |
| the cancel forwarded as the host's stop | timed-out plugin calls never stop | [plugins](05-plugins.md#stopping-a-call) |
| `state.content` read for saved results | empty saved plugin results | [plugins](05-plugins.md#results) |
| elicitation refused | a plugin call hangs | [plugins](05-plugins.md#asking-the-user) |
| one spelling per folder on Windows | one thread split into several sessions | [launch](01-packaging-and-launch.md#windows) |
| the temp folder swept | 5.6 MB left on Windows per start | [launch](01-packaging-and-launch.md#windows) |
| rules re-sent to migrated sessions | an old thread's next turn without its plugin rules | above |
| plain `serve` | a declined turn resumed after a restart | [launch](01-packaging-and-launch.md#launch) |
| the held tools kept under the provider's limit | a request refused for too many functions, and the turn with it | [tool calls](04-tool-calls.md#what-the-opencode-agent-is-offered) |

What is lost regardless is in the [README](README.md#losses).

## Tests

The backend's integration tests already start the staged opencode against a scripted model ([agent](../../architecture/agent.md#tests)); they move to the 2.x routes and shapes and gain a case for each row above. The live sweep reruns the capability list on 2.x before the release ships, and gains a suite with many plugins connected, which measures each model's window share. A retrieval suite of labelled requests over the registry's plugins runs whenever the registry or the embedder changes ([tool calls](04-tool-calls.md#when-a-guess-is-wrong)).

## Docs

The pull request that ships this updates [`agent.md`](../../architecture/agent.md), [`plugins.md`](../../architecture/plugins.md), [`plugin-registry.md`](../../architecture/plugin-registry.md), [`packaging.md`](../../architecture/packaging.md), [`chat.md`](../../architecture/chat.md) and [`claude-plan.md`](../../architecture/claude-plan.md), and [`03-opencode.md`](../agent/03-opencode.md) moves with it. A new ADR records native tool calls, the opencode engine's tool policy and dropping SSE, and supersedes [ADR 0065](../../adr/0065-a-turns-plugin-tools-are-sized-by-the-window-not-counted.md) for opencode; [ADR 0050](../../adr/0050-a-model-answers-on-its-own-route-with-its-connections-credential.md)'s note on moving to 2.x is settled by [the plan's results](06-model-endpoint.md#the-chatgpt-plan).
