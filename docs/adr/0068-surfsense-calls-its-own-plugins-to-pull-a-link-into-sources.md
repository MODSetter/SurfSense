# ADR 0068: SurfSense calls its own plugins to pull a link into Sources, with no agent

- **Status:** Accepted
- **Date:** 2026-10-22
- **Source:** [sources-from-the-web.md](https://github.com/MODSetter/SurfSense/blob/8c0ad2ab6ca8fefa324e28362b669e876e81917d/docs/proposals/sources-from-the-web.md)

## Context

Until now, a plugin's tools were called only by the agent's runtime, through the gateway, in a thread ([ADR 0051](0051-plugins-are-mcp-servers-behind-one-tool-gateway.md), [ADR 0064](0064-agent-runtimes-reach-plugins-through-surfsenses-gateway.md)). SurfSense listed a server's tools itself and never called one. Adding a web page, a video or a product from a link is the user's own action in Sources. It needs no model to choose a tool, and a thread would only stand in the way. Some pulls, such as a video's comments or a place's reviews, take minutes.

## Decision

- **The API calls SurfSense's own plugins for Add from the web.** `McpSession.call_tool` sits beside `list_tools`, on the same SDK client and with the same error translation. It is never retried. Only first-party plugins are called this way, and only for this feature.
- **The license is the gate.** Its key is sent only to the plugin host, as for a connected plugin. No plugin needs to be connected in Settings › Plugins. With no license imported, nothing is asked or sent. The plugin host judges a license that is present.
- **The network question is asked on the user's click.** One consent for the plugin host covers every plugin. A queued pull checks the consent again, and fails rather than asking.
- **Pulls run on the plugins queue.** Its workers wait on the network, and the single ingest worker stays free for indexing. A pulled link becomes a note holding its link, then is indexed like any note.

## Consequences

- **The agent's path is unchanged.** Pausing or disconnecting a plugin in Settings does not stop Add from the web.
- **A call SurfSense makes is not shown in any thread.** Its result is the source itself.
- **Calling third-party plugins this way would need its own decision.** They are signed in per plugin, and the license does not cover them.
