# Tool calls

## Native, not Code Mode

2.x reaches an MCP server's tools through Code Mode unless the server sets `codemode: false`: the model writes JavaScript in one `execute` call that calls `tools.<server>.<tool>(…)` ([tools docs](https://github.com/anomalyco/opencode/blob/v2.1.2/services/www/src/docs/content/tools.mdx), [MCP docs](https://github.com/anomalyco/opencode/blob/v2.1.2/services/www/src/docs/content/mcp-servers.mdx)). SurfSense registers every server with `codemode: false` and denies `execute`, which also removes Code Mode's `fetch`. What Code Mode would cost, from [`core/src/codemode/`](https://github.com/anomalyco/opencode/tree/v2.1.2/packages/core/src/codemode) and measured:

- A call made inside `execute` stores only `{tool, status, input}`: no output, no error text, no files tied to the call. "Created *Title* v1", citations from `surfsense_search_sources` and saved plugin results all read a call's output.
- An approval names the `execute` call, not the call inside it; declining one does not end the turn.
- `fetch` inside `execute` passes no permission or policy, and reaches any loopback port.
- The catalog shown to the model is capped at 2,000 tokens with each description cut to 120 characters, with no setting to change either. With 73 tools it hid `surfsense_search_sources`, `surfsense_create_artifact` and `surfsense_render_document`.
- Qwen3-4B on 40 tools reached the right tool 2 times in 5: it passed strings where objects were required, wrote JavaScript that did not parse and never found a hidden tool with `search()`.

## What the model is offered

Every ready tool, native, on every request: SurfSense's own and every ready plugin's. Each call is one tool item with its own output, error and approval, which is what the step builder, citations and saved results read today.

Measured with Qwen3-4B on llama.cpp at a 32,768 window, 40 tools (SurfSense's 13 and 27 plugin tools) and 5 tasks, each needing a different tool: the right tool with sane arguments 5 times in 5, two requests each. The 40 definitions cost about 6,400 tokens, 8,460 with the system prompt. On the M2 the first request read that in 100 to 170 s; later sessions reused llama.cpp's prompt cache, since the prefix is the same, and answered in 1 to 3 s. Those times hold for that machine only.

## Changes during a turn

2.x builds the tool list before every step from the session's rules as they are then ([`core/src/session/runner/llm.ts`](https://github.com/anomalyco/opencode/blob/v2.1.2/packages/core/src/session/runner/llm.ts), [`core/src/session/context.ts`](https://github.com/anomalyco/opencode/blob/v2.1.2/packages/core/src/session/context.ts)), and re-lists a server 100 ms after it sends `notifications/tools/list_changed` ([`core/src/tool/mcp.ts`](https://github.com/anomalyco/opencode/blob/v2.1.2/packages/core/src/tool/mcp.ts)). So a plugin that connects, a tool a plugin adds, or a rule [`give_plugins.py`](../../../surfsense_local/backend/modules/agent/plugin_tools/give_plugins.py) changes is offered at the next step of the same turn, not the next turn. A change that lands less than about 150 ms before the next step waits one more step.

A tool hidden by a rule and called anyway fails as `No tool named "…" is currently available` and the turn goes on.

## When the tools do not fit

Every tool on every request does not fit a small window once many plugins are connected: 54 plugin tools cost about 7,900 tokens, a quarter of 32,768, on top of SurfSense's 3,900. Two ways, one to choose (README, open question 1):

- **The window budget as a fallback.** Keep [`tool_budget.py`](../../../surfsense_local/backend/modules/agent/plugin_tools/tool_budget.py) only for when the ready tools exceed a tenth of the window, and leave out **whole plugins**, never part of one, saying so as today. A model shown some of a plugin's tools takes them for all of them.
- **On-demand loading**, below, if it holds on the models it would serve.

### On-demand loading

Built to work as Claude Code's tool search does: SurfSense's tools and what fits a tenth of the window load at once, the other tools' names are listed in the `surfsense` server's MCP instructions, which 2.x puts in the system prompt ([`core/src/mcp/instructions.ts`](https://github.com/anomalyco/opencode/blob/v2.1.2/packages/core/src/mcp/instructions.ts)), and `surfsense_find_tools` allows the matched tools on the session before it answers. 2.x has no tool search of its own for native calls; this is SurfSense's.

The mechanics hold, with a scripted model: a found tool is offered at the next step, keeps its output, links its approval and stays offered in the next turn; two plugins load in one search; a plugin that cannot be reached is named as such. The rule change must land before `find_tools` answers; made after, it missed the next step three times in three. Announcing the change with `tools/list_changed` instead works only from a server with its own notification stream, which the gateway does not offer ([plugins](05-plugins.md#tools-added-later)).

The model does not hold: Qwen3-4B, with 21 plugin tools loaded and 33 deferred, called `surfsense_find_tools` in none of 8 tasks. It created no Linear issue and said it had, called `gcal_update_event` to answer "what's on my calendar", and used tools it could already see in place of hidden ones. It passed only the tasks that needed no hidden tool. Each tool loaded mid-turn also re-reads most of the prompt on llama.cpp, 9 to 57 s per load on the M2, because the tool list sits at the start of the prompt. Not measured: a model on the tested list, and leaving out whole plugins rather than splitting one.
