# Tool calls

Tools exist only in Agentic mode; Basic (Q&A) sends none. Agentic runs on two engines, and only one needs SurfSense to choose its tools:

| Engine | Models | Who chooses the tools the model holds |
|---|---|---|
| Claude plan | the user's Claude Code | Claude Code: every ready tool is given, SurfSense's server is always loaded, and Anthropic's tool search defers the rest ([`agent_options.py`](../../../surfsense_local/backend/modules/agent/engines/claude_code/agent_options.py), [claude plan](../../architecture/claude-plan.md)). Unchanged |
| opencode | local models, API models and the ChatGPT plan | SurfSense, by the policy below |

## Native, not Code Mode

2.x reaches an MCP server's tools through Code Mode unless the server sets `codemode: false`: the model writes JavaScript in one `execute` call that calls `tools.<server>.<tool>(…)` ([tools docs](https://github.com/anomalyco/opencode/blob/v2.1.2/services/www/src/docs/content/tools.mdx), [MCP docs](https://github.com/anomalyco/opencode/blob/v2.1.2/services/www/src/docs/content/mcp-servers.mdx)). SurfSense registers every server with `codemode: false`, and denies `execute` by permission. `execute` exists even when no server uses Code Mode, and through it the model would get a `fetch`, opencode's own `session_move` and worktree tools, and a hint to use them.

What Code Mode would cost, from [`core/src/codemode/`](https://github.com/anomalyco/opencode/tree/v2.1.2/packages/core/src/codemode) and measured. The first three hold for any model:

- A call made inside `execute` stores only `{tool, status, input}`: no output, no error text, no files tied to the call. "Created *Title* v1", citations from `surfsense_search_sources` and saved plugin results all read a call's output.
- An approval names the `execute` call, not the call inside it; declining one does not end the turn.
- `fetch` inside `execute` passes no permission or policy, and reaches any loopback port. The docs offer no switch for it but denying `execute`.
- The catalog shown to the model is capped at 2,000 tokens with each description cut to 120 characters, with no setting to change either. With 73 tools it hid `surfsense_search_sources`, `surfsense_create_artifact` and `surfsense_render_document`; a capable model can reach hidden tools with `search()`.
- Qwen3-4B on 40 tools reached the right tool 2 times in 5. A capable model was not measured.

Fixing the first two would take a SurfSense plugin inside opencode recording each nested result; the third needs opencode. As of 22 Oct 2026 neither is changed on opencode's `dev` branch, and the requests are open: per-call identity and records for nested calls ([#54812](https://github.com/anomalyco/opencode/issues/54812)), a policy that can deny `execute` ([#56349](https://github.com/anomalyco/opencode/issues/56349)), asks from inside `execute` that never surface ([#51223](https://github.com/anomalyco/opencode/issues/51223)). Code Mode is revisited for capable models once nested calls keep their output and `fetch` is under permissions.

## Changes during a turn

2.x builds the tool list before every step from the session's rules as they are then ([`core/src/session/runner/llm.ts`](https://github.com/anomalyco/opencode/blob/v2.1.2/packages/core/src/session/runner/llm.ts), [`core/src/session/context.ts`](https://github.com/anomalyco/opencode/blob/v2.1.2/packages/core/src/session/context.ts)), and re-lists a server 100 ms after it sends `notifications/tools/list_changed` ([`core/src/tool/mcp.ts`](https://github.com/anomalyco/opencode/blob/v2.1.2/packages/core/src/tool/mcp.ts)). A rule changed, or a plugin connected, is offered at the next step of the same turn. The change must land before the step starts: made while a tool's result is still on its way back, it is in time; made after the result returned, it missed the next step three times in three. A tool hidden by a rule and called anyway fails as `No tool named "…" is currently available` and the turn goes on.

## What the opencode agent is offered

**Which tools exist for a turn.** SurfSense's built-in tools, always: its own MCP server, not a plugin, registered for every agent thread ([`offered_tools.py`](../../../surfsense_local/backend/modules/agent/tool_endpoint/offered_tools.py)); a model without image input does not get the tools that return images. Plugins, first-party or third-party alike, only when ready: connected and switched on, signed in or licensed where they need it, and reachable at their last check, as [`list_tools()`](../../../surfsense_local/backend/modules/plugins/gateway/listing.py) decides today. A tool the user switched off is never offered.

**When they fit, all of them.** While every ready tool fits the model's share of the window and the provider's limit, every one is offered natively on every request, and nothing below runs. Measured with Qwen3-4B on llama.cpp at a 32,768 window, 40 tools (SurfSense's 13 and 27 plugin tools) and 5 tasks: the right tool with sane arguments 5 times in 5. The 40 definitions cost about 6,400 tokens; the first request read them in 100 to 170 s on the M2 and later sessions reused llama.cpp's prompt cache in 1 to 3 s. A remote model with a large window almost always lands here.

**When they do not fit.** Real MCP tools run to hundreds of tokens each: GitHub's 35 to about 26,000, Slack's 11 to about 21,000 ([Anthropic](https://www.anthropic.com/engineering/advanced-tool-use)). 400 tools from 20 plugins fit no window, and choosing among them degrades even frontier models: one benchmark saw Claude Sonnet fall from 62% to 44% success between 220 and 550 tools ([MCPVerse](https://arxiv.org/abs/2508.16260)). The agent then holds:

1. **The catalogue, always.** Every ready plugin with one line, and its tool names where they fit, in the `surfsense` server's MCP instructions, which 2.x renders into the system prompt ([`core/src/mcp/instructions.ts`](https://github.com/anomalyco/opencode/blob/v2.1.2/packages/core/src/mcp/instructions.ts)). A plugin that cannot be reached is one line saying so. Nothing ready is ever unknown to the agent.
2. **What is always loaded.** SurfSense's built-in tools; plugins the user @-mentioned or pinned; each plugin the user's message names by its catalogue name, with its best-matching tools; and tools the thread has used, which stay until compaction or until their plugin stops being ready. A named plugin is held because the second app of a two-app request is what retrieval misses most ([measured](#retrieval-measured)).
3. **What is retrieved.** The rest is chosen by search over the ready tools: keyword and embedding search with the embedder SurfSense already runs ([embedding](../../architecture/embedding.md), [search](../../architecture/search.md)), merged by reciprocal rank fusion rather than the semantic weighting source search uses, which ranked tools worse. Each tool is indexed with its name, description, parameters, its plugin's line and its example requests. The query is the user's message and the previous turn. Tools are ranked one by one and taken in rank order until the share is spent. Retrieval runs again after each plugin call, inside the gateway before the result goes back, so a tool the task turns to is there at the next step. Within a turn tools are only added, never removed.
4. **A way to ask.** `surfsense_open_plugin(name)`, choosing from the catalogue's plugins, and `surfsense_find_tools(query)`. Either allows the matched tools before it answers. They serve models that use them; nothing depends on a model using them.

Everything else is hidden by a session rule, as [`give_plugins.py`](../../../surfsense_local/backend/modules/agent/plugin_tools/give_plugins.py) hides tools today. Every call is still one native tool item with its own output and approval.

**Searching and pre-loading share one index.** `surfsense_find_tools` is SurfSense's counterpart of Claude Code's tool search, and like it needs an index of the tools to search; retrieval runs the same search on the user's message before the model asks. Claude Code can rely on the model searching because Claude is trained to; the opencode engine serves models that do not, so the likely tools are loaded first and searching stays for what that missed. A model a capability suite shows to search reliably can later be given only the always-loaded set and the search, as Claude Code is.

**How much the agent holds** is a share of the model's window: by default at least 8,000 tokens of plugin tools where the window allows, which held every needed tool for 90% of realistic tasks, and about a quarter of a small window, so a larger window holds more with nothing kept per model; and a model's own share once a capability suite with many plugins connected has measured it ([capability levels](../../architecture/model-capabilities.md)). There is no hand-kept table of model tiers: what a model of a given size handles shifts with each release and quantization. The held set never exceeds the provider's own limit on tools per request where it has one: 128 on OpenAI's chat completions and on Vertex, 512 on the Gemini API, 350 on xAI; Anthropic, OpenAI's Responses API and llama.cpp document none. The count includes opencode's and SurfSense's own tools.

This replaces [ADR 0065](../../adr/0065-a-turns-plugin-tools-are-sized-by-the-window-not-counted.md)'s budget for opencode: nothing ready is left out of the agent's view, and a plugin is no longer reachable only by an @-mention.

## Native tool search

Anthropic's and OpenAI's APIs search deferred tools themselves, for Claude 4.5 and later and GPT-5.4 and later: the model sees names, the provider loads definitions when the model asks, and the prompt cache holds ([Anthropic](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool), [OpenAI](https://developers.openai.com/api/docs/guides/tools-tool-search)).

- **The Claude plan** has it through Claude Code today.
- **The ChatGPT plan** cannot have it. Its endpoint refuses `tool_search`, hosted or run by the client, before the model runs: `tool 'tool_search' is not supported. Remove it or use an API key instead.` It accepts only `web_search`, functions and custom tools, namespaces, and `programmatic_tool_calling`. Checked on 22 Oct 2026 with `gpt-5.6-luna`. It takes the policy above; with a 272,000-token window its tools almost always fit.
- **API models through opencode** need opencode to send deferred tools, which 2.x does not ([#45527](https://github.com/anomalyco/opencode/issues/45527)). When it does, Claude and GPT models that support it move from the policy to their provider's search. Doing it in the model endpoint instead, for an OpenAI API key, is not tested: whether opencode keeps the search items OpenAI returns, and replays them, is unknown.

## Measured on the way

- **A search tool alone does not reach a small model.** With 21 plugin tools loaded and 33 hidden behind `surfsense_find_tools`, Qwen3-4B called it in none of 8 tasks. It created no Linear issue and said it had, called `gcal_update_event` to answer "what's on my calendar", and used tools it could see in place of hidden ones. The split left part of one plugin visible, which it took for the whole plugin. No published result shows a model under 10B calling a free-text search tool reliably ([LiveMCPBench](https://arxiv.org/abs/2508.01780) finds retrieval behind half of all failures; Microsoft lists "the model never calls `tool_search`" as a known failure of its own). This is why retrieval, not the model, does most of the choosing, and why tools are chosen by whole plugin.
- **Each tool added mid-turn costs a local model a re-read.** 2.x sorts native tools by name and llama.cpp reuses a prompt only up to its first changed token, so an added tool re-reads the prompt from where it sorts: 9 to 57 s per load on the M2.

## When a guess is wrong

No number in this design has to be right for it to work: each has a cautious default, a miss has somewhere to go, and measurement improves the numbers without changing the design.

**Retrieval misses a tool.** Retrieval is not the only way in.

- A plugin the message names is held whatever retrieval ranks.
- Tools are indexed with example requests besides their name, description and parameters. SurfSense writes them for its own plugins; a registry entry can carry them in an optional field ([plugins](05-plugins.md#example-requests)); a custom plugin is indexed without.
- Tools a user calls often rank higher, and tools a thread used stay held, as Microsoft's Foundry pins each user's most-called tools ([Foundry](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/tool-search)).
- The catalogue names every ready plugin, @-mentions and pins still load one, and a hidden tool the model calls is caught (below).
- A retrieval suite of labelled requests over the registry's plugins runs whenever the registry or the embedder changes, so how often retrieval holds is tracked, not assumed. It needs no language model.

**The model does not ask.** Tools reach it without its help.

- Retrieval at the turn's start and after each plugin call holds the right tool most of the time.
- The catalogue names every tool, and a model calls tools it sees named. When it calls a hidden one, opencode refuses the call as `No tool named "…" is currently available`. SurfSense reads that failure from the event stream and allows the tool if its plugin is ready; the model has it from the step after next, since opencode starts the next step before the rule can land. This needs no skill of the model.
- `surfsense_open_plugin` and `surfsense_find_tools` add to that for models that use them.

**What the user sees.** Loading tools is never shown as an error, and appears only among the agent's steps in the thread ([`agent-steps.tsx`](../../../surfsense_local/frontend/src/features/agent/agent-steps.tsx)), nowhere else:

- A hidden tool the model called and SurfSense then allowed is not a failed step. Its refused call becomes one step, "Loaded Linear's tools", and the real call follows as its own step.
- `surfsense_open_plugin` and `surfsense_find_tools` show the same way, "Loaded Linear's tools", or "Looked for tools to …" when nothing new was loaded.
- Loading at the turn's start and the re-run after a plugin call show nothing.
- "Not all of {plugin}'s tools fit this turn. Mention it with @ to use them all." goes ([`plugins-unavailable.tsx`](../../../surfsense_local/frontend/src/features/agent/plugins-unavailable.tsx)): nothing ready is out of the agent's reach. "Couldn't reach {plugin}" stays, since it says something the user can act on.
- An @-mention still holds a plugin's tools, as an override; the agent no longer needs one to know a plugin is there.

**Each change costs a local model a re-read.** The held set changes rarely and in batches.

- It is chosen generously at the turn's start.
- Mid-turn it grows only when it must: retrieval after a plugin call finds another plugin, the model asks, or a hidden tool is caught.
- It grows by whole plugin, never a tool at a time.
- SurfSense's built-in tools and the always-loaded set stay fixed.

The rule is the same on every machine; only the seconds differ by hardware. Upstream, opencode keeping the order tools were added in, or sending deferred tools ([#45527](https://github.com/anomalyco/opencode/issues/45527)), would turn each re-read into an append. A remote provider's cache is affected only from the point of change.

**The share is wrong for a model.** It is a cautious default until the model is measured, and never more than the provider's limit.

## Retrieval, measured

Offline on 22 Oct 2026, with no language model: SurfSense's own encoder (bge-small) and the keyword search of [`shared/search.py`](../../../surfsense_local/backend/shared/search.py), over two sets of real tools.

- **SurfSense-like:** 16 plugins, 522 tools, about 123,000 tokens, from the `tools/list` of GitHub's MCP server, Notion, Sentry, Stripe, HubSpot, Google Calendar, Gmail and others, with community servers for Linear (198 tools), Atlassian and Asana. 87 requests, 35 of them needing 2 to 4 tools.
- **[LiveMCPBench](https://github.com/icip-cas/LiveMCPBench):** 69 servers, 525 tools, 94 labelled tasks whose requests rarely name the app.

Tasks with every needed tool held, best configuration (fusion, example requests, previous turn in the query):

| Plugin-tool share | Tools held | All tasks | One-tool tasks | Multi-tool tasks |
|---|---|---|---|---|
| 2,000 tokens | about 9 | 75% | 94% | 46% |
| 4,000 | about 16 | 82% | 100% | 54% |
| 8,000 | about 30 | 90% | 100% | 74% |
| 16,000 | about 58 | 98% | 100% | 94% |

On LiveMCPBench, leaving out tools opencode already has (writing files, fetching pages), 50 to 60% at 4,000 tokens and 73 to 78% at 8,000.

- Example requests were the largest gain, 10 to 17 points at every share. Fusion beat the 0.65 weighting by 0 to 8 points. The previous turn added 2 to 3, and fixed follow-ups such as "now the other one".
- Choosing plugins before tools, capping tools per plugin and loading a small plugin whole gained nothing or lost.
- Re-running mid-turn added 0 to 4 points on the SurfSense-like set, where the message dominates the query, and 20 to 25 points once the agent was in the right plugin, where the next tool is a sibling of the last.
- Misses were mostly the second app of a two-app request (10 of 11 at 8,000 tokens), then generic tools nobody names, vocabulary such as "deal" against HubSpot's `search-objects`, and a large plugin's generic verbs crowding others.
- About 20 ms per query on an M2 for 522 tools; indexing about 0.07 s per text.

What the numbers cannot say: the requests were written and labelled by one person and name their app more than users may; the example requests were written by a capable model, not one running on the user's machine; and whether a held tool is then called well depends on the model, which the capability suites measure.
