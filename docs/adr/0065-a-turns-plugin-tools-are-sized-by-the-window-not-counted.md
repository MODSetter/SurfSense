# ADR 0065: A turn's plugin tools are sized by the model's window, not counted, and Claude Code searches its own

- **Status:** Accepted; superseded for the opencode engine (its budget, its left-out notice and its note to the agent) by [ADR 0069](0069-opencode-calls-tools-natively-and-holds-what-a-turn-needs.md)
- **Date:** 2026-10-20
- **Source:** maintainer decision, 20 Oct 2026 (no permalink)

## Context

Each agent turn offered at most 24 plugin tools, the plugins connected first winning. No measurement set the number. A plugin with many tools took most of it: with Notion's 29 tools on, a later context7 was offered nothing, and the agent told the user it was not connected.

The limit exists because a model can call only the tools in its request, and a runtime that sends every definition with every request spends the window on them; small local models, which SurfSense runs at windows as small as 32k, also choose worse from long lists. The two runtimes differ here:

- Claude Code searches its own MCP tools. It loads only their names, and a definition when the model asks for it, and documents no tool limit beyond the window ([Claude Code docs](https://code.claude.com/docs/en/mcp#scale-with-mcp-tool-search)).
- opencode 1.18.34 adds every MCP tool's definition to every request. Its only search is in its experimental code mode, behind `OPENCODE_EXPERIMENTAL_CODE_MODE`, which 2.x made the default for MCP servers.

## Decision

- **No count.** Neither runtime is limited to a number of tools.
- **Claude Code is given every ready tool** and finds them with its own tool search. `ENABLE_TOOL_SEARCH` is set to `auto`, so an update cannot change it: tools load up front under a tenth of the window, and are all deferred past it. SurfSense's own server is always loaded.
- **opencode is given what fits a tenth of the model's window,** the same share Claude Code defers at, each tool costed by its definition's length. A mentioned plugin's tools go first, whatever they cost; then the plugins take turns, one tool each, so no plugin crowds out the rest, the tools the user's message matches first, scored as opencode's code-mode search scores them.
- **A plugin left out is said,** to the user in the turn's notice and to the agent in a note naming how to bring it in: a mention.
- **No search of SurfSense's own on opencode 1.x.** Measured on 1.18.34 on 20 Oct 2026: a session rule allowing a tool mid-turn changes nothing until the next turn, since opencode fixes a turn's tools when it starts, so a tool the model searched for could not be offered to it. Choosing by the message, before the turn, is the search 1.x allows. opencode 2.x's code mode, whose `search(...)` runs mid-turn, would replace the budget.

## Consequences

- Connecting more plugins never hides one silently, and a Claude plan thread can use any of them.
- An opencode turn on a small local model offers a few tools, and one on a large remote model many more.
- An opencode turn still cannot reach a tool it was not offered without the user's mention.
- A Claude Code turn with many tools takes a search step before calling one it has not loaded.
