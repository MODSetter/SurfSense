# ADR 0068: On opencode 2.x the agent calls tools natively, holds the plugin tools its task needs from a catalogue of every ready plugin, and no plugin speaks SSE

- **Status:** Accepted
- **Date:** 2026-10-22
- **Supersedes:** [ADR 0065](0065-a-turns-plugin-tools-are-sized-by-the-window-not-counted.md) for the opencode engine: its budget, its left-out notice and its note to the agent. Claude Code's part stands.
- **Source:** [opencode `core/src/session/runner/llm.ts` at v2.1.2](https://github.com/anomalyco/opencode/blob/v2.1.2/packages/core/src/session/runner/llm.ts), [`core/src/codemode/`](https://github.com/anomalyco/opencode/tree/v2.1.2/packages/core/src/codemode), [`core/src/mcp/instructions.ts`](https://github.com/anomalyco/opencode/blob/v2.1.2/packages/core/src/mcp/instructions.ts); measurements of 22 Oct 2026

## Context

The agent's runtime moved from opencode 1.18.34 to 2.1.2. Three things changed that decide how its tools are given:

- 2.x builds a step's tool list from the session's rules as they are when the step starts, so a tool allowed mid-turn is offered at the next step. 1.x fixed a turn's tools when it started, which is why ADR 0065 chose before the turn and named what it left out.
- 2.x reaches an MCP server's tools through Code Mode by default: the model writes code in one `execute` call. A call made inside it stores no output, its approval names only `execute`, its `fetch` passes no permission, and its catalogue is capped at 2,000 tokens. With 40 tools Qwen3-4B reached the right tool 2 times in 5 under Code Mode and 5 in 5 with native calls.
- 2.x's MCP client speaks Streamable HTTP only, and MCP deprecated SSE in 2025.

Measured offline over 522 real tools from 16 plugins and 87 requests, keyword and embedding search fused by reciprocal rank held every needed tool for 90% of tasks at 8,000 tokens of plugin tools. That run gave every tool example requests, the largest single gain at 10 to 17 points; no registry entry carries any, and examples on some plugins only would rank those ahead for words the others lack. A small model given only a search tool called it in none of 8 tasks.

## Decision

- **Native calls.** Every MCP server is added with `codemode: false`, and `execute` is denied. Each call is its own step, with its own output and approval.
- **All the ready tools, while they fit.** SurfSense's own tools are always held. While every ready plugin tool fits a quarter of the model's window and the provider's limit on tools per request, all are held.
- **Past that, a catalogue and what the task needs.** Every ready plugin is named in the instructions of SurfSense's MCP server, which opencode puts in the system prompt. The turn holds mentioned plugins whole, the best tools of plugins its message names, the tools the thread used since it last compacted, and what keyword and embedding search ranks highest for the message and the turn before, until the share is spent. Tools are indexed by their name, description, parameters and plugin's line, which every plugin has; there are no example requests.
- **A turn's tools grow, and never shrink.** After each plugin call the gateway holds the rest of that plugin and the plugin of the best tool not held, before the result goes back. A call to a tool not held is refused by opencode; SurfSense holds its plugin and shows the step as loading it. `surfsense_open_plugin` and `surfsense_find_tools` hold more on request. Holdings grow by whole plugin, since each change makes a local model read its prompt again.
- **No SSE.** SurfSense's MCP client, both engines and the registry speak Streamable HTTP only. A plugin installed over SSE is moved to its `/mcp` address at its first check; one that serves only SSE is refused.
- **The ChatGPT plan** stays pointed at SurfSense's `/responses`, as ADR 0050 expected: checked against a real plan on 2.1.2, every step, reasoning replay and refusal behaved as on 1.x. Its endpoint refuses `tool_search`, so it takes this policy.

## Consequences

- Nothing ready is unknown to the agent, and no plugin needs an @-mention to be reached. The "Not all of a plugin's tools fit this turn" notice is gone.
- A local model with many plugins connected holds tens of tools, and re-reads its prompt each time a turn's holding grows.
- What the agent holds depends on retrieval, which ranks without the example requests that gained most offline. They come back only in a form every plugin can have.
- Plugins that speak only SSE no longer work on either engine.
- Code Mode is revisited once opencode keeps nested calls' output and puts `fetch` under permissions; API models move to their provider's own tool search once opencode can send deferred tools.
