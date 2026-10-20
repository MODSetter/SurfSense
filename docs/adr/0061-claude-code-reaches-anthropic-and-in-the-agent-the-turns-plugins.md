# ADR 0061: Claude Code reaches Anthropic's two hosts, and in the agent also the hosts of the turn's ready plugins

- **Status:** Accepted; an agent run reaching the plugins' hosts and holding their sign-in headers is superseded by [ADR 0063](0063-agent-runtimes-reach-plugins-through-surfsenses-gateway.md)
- **Date:** 2026-10-16

## Context

[ADR 0057](0057-a-claude-plan-runs-through-the-users-own-claude-code.md) has Claude Code's traffic tunnel "only `api.anthropic.com`". Claude Code also refreshes its sign-in on `platform.claude.com`, so chat runs already allow both, each while the user allows it ([ADR 0060](0060-one-consent-question-per-user-action.md)).

The agent gives Claude Code the thread's plugins. opencode connects to each plugin server itself, with its URL and sign-in header, through the plugin proxy, which passes only a ready plugin's hosts ([agent](../architecture/agent.md#network)). Measured on Claude Code 2.1.301: its MCP traffic to a remote plugin goes through `HTTPS_PROXY`, so a proxy limited to Anthropic refuses the plugin.

The alternative was for SurfSense's tool endpoint to list and forward plugin tools, so Claude Code would reach only Anthropic. SurfSense has no code that forwards an MCP call; it would be a second MCP client beside opencode's, with its own sessions, timeouts and cancellation, to keep plugin tokens out of a process that opencode already gives them to.

## Decision

- A chat run's Claude Code reaches `api.anthropic.com` and `platform.claude.com`, each while its destination is on, and nothing else. A chat run is given no MCP server.
- An agent run's Claude Code reaches the same two hosts and the hosts of the ready plugins, by the check the plugin proxy applies to opencode. It connects to each plugin server itself, as opencode does.
- The two run kinds use separate proxies, so a chat run can never reach a plugin host.
- The MCP servers, with their sign-in headers, are passed to Claude Code in a file only the user can read, never on its command line.

## Consequences

- Claude Code reaches no host the user has not allowed for the same purpose in opencode.
- Claude Code holds the sign-in headers of the plugins it is given for the life of its process, as opencode does.
- A change to how the plugin proxy decides readiness applies to both engines.
- This supersedes ADR 0057's "tunnels only `api.anthropic.com`".
