---
status: proposed
code:
  - surfsense_local/electron/scripts/opencode/
  - surfsense_local/electron/src/main/sidecars/
  - surfsense_local/backend/modules/agent/
  - surfsense_local/backend/modules/plugins/
  - surfsense_local/frontend/src/features/agent/
  - plugins/registry/
---

# opencode 2.x

> The agent's runtime moves from opencode `1.18.34` to `2.1.2`. Tool calls stay native: every MCP server is registered with `codemode: false` and `execute` is denied, so each call is its own step with its own output and approval. SurfSense's built-in tools are always loaded and plugins only when ready; when they all fit they are all offered, and when they do not the agent sees every plugin in a catalogue and holds what SurfSense retrieves for the task, changing between steps of a turn. Plugins that speak only the older SSE transport are no longer supported, on either engine.

opencode's 2.x line changes three contracts SurfSense depends on: the server API, the plugin API and the terminal client's settings ([migration guide](https://github.com/anomalyco/opencode/blob/v2.1.2/services/www/src/docs/content/migrate-v1.mdx)). SurfSense ships no opencode plugin and uses no terminal client, so the server API is the break; the configuration keeps loading in 1.x syntax but moves to the native shape. [`03-opencode.md`](../agent/03-opencode.md) describes what is built on 1.x.

Facts below were checked against opencode at tag [`v2.1.2`](https://github.com/anomalyco/opencode/tree/v2.1.2) (commit `a517687`), published on npm on 21 Oct 2026, and measured on 22 Oct 2026 by running that binary: on macOS (Apple M2, 8 GB), on Windows 11 build 26300 with Defender real-time protection on, against a scripted model, against Qwen3-4B-Instruct-2507 on the llama.cpp the app pins, through the repo's real plugin gateway, and against a real ChatGPT plan through a dev build. Source paths are under `packages/` unless they say otherwise.

## Parts

| Part | File | Owns |
|---|---|---|
| Packaging and launch | [`01-packaging-and-launch.md`](01-packaging-and-launch.md) | the npm tarballs, staging, the environment, leftovers, Windows |
| Server API and the turn | [`02-server-api.md`](02-server-api.md) | routes, events, messages, the backend's client and the readers built on it |
| Configuration and permissions | [`03-config-and-permissions.md`](03-config-and-permissions.md) | the native configuration file, rules, policies, verification |
| Tool calls | [`04-tool-calls.md`](04-tool-calls.md) | native calls, what the model is offered, mid-turn changes, Code Mode |
| Plugins | [`05-plugins.md`](05-plugins.md) | the gateway on 2.x's MCP client, SSE, cancel, results, names |
| Model endpoint | [`06-model-endpoint.md`](06-model-endpoint.md) | what opencode now does itself, what SurfSense keeps, the ChatGPT plan |
| Migration and rollout | [`07-migration-and-rollout.md`](07-migration-and-rollout.md) | existing threads, losses, the regressions each step must hold, docs |

## Decisions

- **Native tool calls, not Code Mode.** Code Mode is 2.x's default for MCP servers. For any model it stores no output for the calls it makes, links an approval only to the outer `execute` call and gives model-written code a `fetch` no permission covers; it also lists at most 2,000 tokens of tools. On 40 tools Qwen3-4B reached the right tool 2 times in 5 under Code Mode and 5 in 5 with native calls. It is revisited when opencode keeps nested calls' output and puts `fetch` under permissions ([tool calls](04-tool-calls.md#native-not-code-mode)).
- **One tool policy for the opencode engine.** Basic mode has no tools, and the Claude plan engine keeps Claude Code's own tool search. In opencode threads, SurfSense's built-in tools are always loaded and plugins, first-party or third-party, only when ready. While the ready tools fit the model's share of the window and the provider's limit, all are offered. Past that the agent sees every plugin in a catalogue and holds its built-in tools, mentioned or pinned plugins, plugins its message names, tools the thread used, and what SurfSense retrieves for the task with keyword and embedding search over tools and their example requests, with `surfsense_open_plugin` and `surfsense_find_tools` to ask for more. At 8,000 tokens of plugin tools retrieval held every needed tool for 90% of realistic tasks. There is no hand-kept table of model tiers ([tool calls](04-tool-calls.md#what-the-opencode-agent-is-offered)).
- **Native tool search where the provider gives it.** The Claude plan has it today. The ChatGPT plan's endpoint refuses `tool_search`, so it takes the policy above. API models move to their provider's search once opencode can send deferred tools ([tool calls](04-tool-calls.md#native-tool-search)).
- **SSE-only plugins are dropped, on both engines.** opencode 2.x's MCP client speaks Streamable HTTP only, and the Claude plan engine refuses them too so a thread behaves the same on either ([plugins](05-plugins.md#sse)).
- **Plain `serve`.** `serve --service` resumes an interrupted turn after a restart, including one the user declined ([launch](01-packaging-and-launch.md#launch)).
- **Todos stay on.** 2.x turns `todowrite` off unless `experimental.todo` is set; 1.x offers it today, and the thread shows its steps as "Updated its plan" ([configuration](03-config-and-permissions.md#keys)).

## What gets better

- Tools, permissions and plugins can change during a turn: opencode reads session rules before every step and re-lists a server that sends `tools/list_changed` ([`core/src/session/runner/llm.ts`](https://github.com/anomalyco/opencode/blob/v2.1.2/packages/core/src/session/runner/llm.ts)). 1.x fixed a turn's tools when it started, which is why a turn today says "Not all of a plugin's tools fit this turn".
- Malformed tool arguments are repaired by opencode ([`core/src/plugin/tool-input-repair.ts`](https://github.com/anomalyco/opencode/blob/v2.1.2/packages/core/src/plugin/tool-input-repair.ts)); long tool output is cut at 50 KB with the whole kept in a file the part names.
- An interrupted or timed-out MCP call sends `notifications/cancelled` to its server, and every call carries the session id in `_meta`.
- The configuration file is watched and reloads without a restart; a turn ends with a recorded outcome; policies give a deny that no session rule or saved approval can lift.
- On the chat completions route opencode sends one system message, skips empty assistant turns and retries a stream cut short, which the model endpoint does by hand today.
- On a ChatGPT plan a turn's reasoning is replayed across steps and turns.

## Losses

What 2.x gives up that 1.x had, and no setting restores:

1. Plugins that speak only HTTP+SSE.
2. The `doom_loop` ask on the third identical call in a row.
3. A user's reason for declining a plugin tool: the model sees only "Unable to execute `<tool>`".
4. MCP progress: it no longer extends a call's timeout, so a plugin call's limit is a hard cap.

## Open questions

1. Whether the SSE-only providers users have connected offer a Streamable HTTP address, so dropping SSE costs a reconnect rather than the plugin.
