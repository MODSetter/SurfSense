# ADR 0064: Agent runtimes reach plugins only through SurfSense's gateway, and never hold a plugin's credential

- **Status:** Accepted
- **Date:** 2026-10-20
- **Supersedes:** [ADR 0061](0061-claude-code-reaches-anthropic-and-in-the-agent-the-turns-plugins.md) in part: an agent run's Claude Code reaching the ready plugins' hosts, connecting to each plugin server itself, and holding their sign-in headers.
- **Source:** maintainer decision, 20 Oct 2026 (no permalink)

## Context

opencode and Claude Code each connected to a plugin's server themselves, given its URL and its sign-in as headers: a pasted key, header values, or an OAuth access token. Their traffic left through a `CONNECT` proxy that tunnelled only to a ready plugin's hosts, so SurfSense saw the host and never the content ([agent](../architecture/agent.md#network)). That proxy replaced one that refused everything, once plugins needed to reach remote servers.

ADR 0061 weighed SurfSense forwarding the calls instead, and turned it down as a second MCP client beside opencode's, with its own sessions, timeouts and cancellation. Three needs have since appeared that a tunnel cannot meet:

- A user moves between runtimes in SurfSense: a thread runs on opencode or Claude Code by the model chosen, and hands over when it changes. A plugin is SurfSense's, connected once, so its sign-in belongs in one place every runtime reaches the same way, not copied into whichever runtime a turn runs on.
- A tool call refused with `403 insufficient_scope` is inside the tunnel, so the plugin never shows it needs more access.
- An OAuth token that expires mid-turn cannot be refreshed. Refreshing it before a turn changes the headers, so opencode reconnects and a stateful plugin loses its session.

## Decision

- **No plugin credential reaches an agent runtime.** A key, a header value, an OAuth token or a license key stays encrypted in SurfSense's database. It is decrypted only in the API, for the request it is sent on.
- **A runtime is given the gateway, not the server.** Each plugin is `http://<API>/agent/plugins/workspaces/<workspace>/threads/<thread>/<plugin>`, with a key for that thread's plugins alone. The key is derived from the API process's launch key, so it opens neither the model endpoint nor SurfSense's tools, and dies with the process. It is per thread, not per turn, so a runtime keeps its MCP session with a plugin across turns.
- **The gateway forwards HTTP, not MCP.** It checks the plugin is ready on every request, sends the request on with the plugin's sign-in, and streams the answer back as it came. It reads the status and headers, and only which tool a call names, so the runtime's MCP client keeps its own sessions, timeouts and cancellation, the objection ADR 0061 raised.
- **The gateway answers what the tunnel could not:**
  - On an OAuth plugin's `401`, it refreshes the token once and sends the request again.
  - On a `403 insufficient_scope`, it records the scopes the server asked for, as a check does, and the turn names the plugin as needing more access; a refused refresh names it as needing a sign-in.
  - A call naming a tool the user blocked since the turn began is answered as a failed call, and never reaches the server.
  - For a server on the older SSE transport, it rewrites the stream's `endpoint` event to point back at itself, so every message passes through it.
- **The proxy keeps only its refusal.** opencode's proxy passes no host, and an agent run's Claude Code uses the chat run's proxy, which passes Anthropic's two hosts alone. Neither runtime reaches a plugin's host.

## Consequences

- Neither runtime's configuration, files or memory holds a plugin's credential, and a thread that switches runtime reaches its plugins the same way on both.
- SurfSense sees the content of plugin calls. They never leave the machine to reach it: the API already holds the credentials and lists the same servers.
- A plugin switched off, or a host revoked, is refused at the runtime's next request rather than its next connection.
- Every plugin call takes one more loopback hop, and the API holds each open stream for as long as the runtime does.
- A server that reports missing access inside a tool's result, rather than as a `403`, is still not seen.
