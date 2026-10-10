# ADR 0051: A plugin is an MCP server, and every caller reaches plugin tools through one Tool Gateway, remote servers first

- **Status:** Proposed, with the [plugins proposal](../proposals/plugins/README.md)
- **Date:** 2026-10-08
- **Source:** maintainer decision, 8 Oct 2026 (no permalink); [Pi's built-in MCP extension](https://github.com/earendil-works/pi/blob/ce950d78f424dcaf9f5d6a03ce80ab141130eb1d/packages/coding-agent/src/extensions/mcp/index.ts), [Pi's MCP client](https://github.com/earendil-works/pi/blob/ce950d78f424dcaf9f5d6a03ce80ab141130eb1d/packages/mcp/README.md)

## Context

The first plugin design made a plugin a sidebar action with a form. Its only output was notes in Sources, which the chat and the agent reached by searching ([earlier design](../proposals/plugins/bundles/README.md)). No engine could call a plugin, a note went stale once written, and every plugin was code in this repository published with app releases, so only SurfSense could grow the set.

The agent already calls SurfSense's own tools over MCP ([agent](../architecture/agent.md#surfsenses-tools)). Many companies already run MCP servers that every MCP client connects to. Pi keeps one tool pipeline of its own and adapts MCP servers into it as one source among others, through its own small client. Claude's connectors list remote MCP servers and package local ones as MCP Bundles.

## Decision

- A plugin is an MCP server. SurfSense speaks MCP unmodified and defines no protocol of its own.
- One Tool Gateway in the API is the only way any caller reaches a plugin tool: opencode, the chat engine's router step, and `@` mentions. Approval, policy, logging, trimming and storing results live there.
- Behind the gateway, sources implement one interface. The first is a remote MCP server over HTTPS, hosted by its publisher, which may be SurfSense, a company or a community developer. Plugins that run on the user's machine come later as bundles behind the same interface.
- A tool's result returns into the turn and is stored with the call. Nothing reaches Sources unless the user saves it.
- The API carries a small MCP client of its own rather than the official SDK.
- No plugin code runs inside the app, and a plugin cannot change SurfSense's own behaviour.

## Consequences

- An existing MCP server becomes a SurfSense plugin with a registry entry and no new code.
- Both engines and the user get one set of tools; adding a kind of source changes none of them.
- What a tool is sent leaves the machine for its publisher's host. Plugins are optional, and the app keeps working offline without them; offline plugins wait for bundles.
- SurfSense cannot see or check a remote server's code. Review of the listing, egress consent, approval and delisting are the controls.
- The local runner, SDK and CLI built for the earlier design are kept for bundles, not wired in.

## Where the code stands

Nothing of the gateway, the client or the plugin tables exists. `modules/plugins/` holds the earlier design's runner, and `plugins/bundles/core/` its SDK, CLI and manifest rules.
