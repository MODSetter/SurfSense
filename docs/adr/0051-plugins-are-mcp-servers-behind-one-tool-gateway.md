# ADR 0051: A plugin is an MCP server, and SurfSense decides which of its tools each caller gets, remote servers first

- **Status:** Accepted
- **Date:** 2026-10-08
- **Source:** maintainer decision, 8 Oct 2026 (no permalink); [Pi's built-in MCP extension](https://github.com/earendil-works/pi/blob/ce950d78f424dcaf9f5d6a03ce80ab141130eb1d/packages/coding-agent/src/extensions/mcp/index.ts), [Pi's MCP client](https://github.com/earendil-works/pi/blob/ce950d78f424dcaf9f5d6a03ce80ab141130eb1d/packages/mcp/README.md)

## Context

The first plugin design made a plugin a sidebar action with a form. Its only output was notes in Sources, which the chat and the agent reached by searching ([earlier design](../proposals/plugins/bundles/README.md)). No engine could call a plugin, a note went stale once written, and every plugin was code in this repository published with app releases, so only SurfSense could grow the set.

The agent already calls SurfSense's own tools over MCP ([agent](../architecture/agent.md#surfsenses-tools)). Many companies already run MCP servers that every MCP client connects to. Pi keeps one tool pipeline of its own and adapts MCP servers into it as one source among others, through its own small client. Claude's connectors list remote MCP servers and package local ones as MCP Bundles.

## Decision

- A plugin is an MCP server. SurfSense speaks MCP unmodified and defines no protocol of its own.
- SurfSense decides, in one place, which plugin tools each caller gets and which must be approved.
- The agent's opencode is an MCP client, so it calls plugin servers itself: before each turn SurfSense gives it the ready servers, their sign-in, and an `allow`, `ask` or `deny` rule per tool, every unreviewed tool denied. The calls and their results are kept in the thread's opencode session. SurfSense is in no call's path, so the agent's calls keep opencode's speed, sessions, progress and cancellation.
- SurfSense's own callers, the chat engine's router step later, reach plugin tools through one Tool Gateway, where policy and approval live, and which records the calls it makes, since nothing else keeps them.
- Behind the gateway, sources implement one interface. The first is a remote MCP server over HTTPS, hosted by its publisher, which may be SurfSense, a company or a community developer. Plugins that run on the user's machine come later as bundles behind the same interface.
- A tool's result returns into the turn. Nothing reaches Sources unless the user saves it.
- The API uses the official MCP Python SDK's client, pinned to one minor version and wrapped in one folder.
- No plugin code runs inside the app, and a plugin cannot change SurfSense's own behaviour.

## Consequences

- An existing MCP server becomes a SurfSense plugin with a registry entry and no new code.
- The agent and the user, and later the chat engine, get one set of tools; adding a kind of source changes none of them.
- What a tool is sent leaves the machine for its publisher's host. Plugins are optional, and the app keeps working offline without them; offline plugins wait for bundles.
- SurfSense cannot see or check a remote server's code. Review of the listing, egress consent, approval and delisting are the controls.
- For the agent, SurfSense's checks run per turn, not per call: a host revoked mid-turn is refused from the next turn, and a reviewed tool's description reaches the model uncut.
- The local runner, SDK and CLI built for the earlier design are kept for bundles, not wired in.

## Where the code stands

Built for remote servers ([plugins](../architecture/plugins.md)): the MCP client's listing, the gateway's readiness and approval rules, the plugin tables and the `/plugins` routes are in `surfsense_local/backend/modules/plugins/`, and `modules/agent/plugin_tools/` gives the agent's opencode the ready servers and their rules each turn ([agent](../architecture/agent.md#plugins)). There is no interface for sources yet, only the remote one. The gateway's call path and a table of calls come with the chat engine ([proposal](../proposals/plugins/README.md#the-chat-engines-router-step)). `modules/plugins/bundles/` holds the earlier design's runner, and `backend/plugins/bundles/core/` its SDK, CLI and manifest rules.
