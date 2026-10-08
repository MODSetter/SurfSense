---
status: proposed
code:
  - surfsense_local/backend/modules/plugins/mcp_client/
  - plugins/proprietary/surfsense-scrapers/
  - plugins/registry/
---

# Remote plugins

> The first kind of plugin. A remote plugin is an MCP server its publisher hosts, SurfSense, a company or a community developer, and the app connects to it over HTTPS. Nothing of it runs on the user's machine. What every kind of plugin shares, the gateway, the list, the engines, approval and paid access, is in [`../core/`](../core/01-architecture.md); plugins that run on the user's machine are [bundles](../bundles/README.md).

## Files

| File | Covers |
|---|---|
| [`01-mcp-client.md`](01-mcp-client.md) | The app's MCP client, signing in, credentials, egress |
| [`02-surfsense-servers.md`](02-surfsense-servers.md) | The servers SurfSense publishes and hosts, starting with SurfSense Scrapers |

## How one works

```
plugins.json entry ──► Settings → Plugins ──Connect──► egress consent ──► sign in (OAuth, token or license)
                                                                              │
opencode ─MCP─► /agent/plugin-tools ─┐                                         ▼
chat engine ─► router step ──────────┼──► Tool Gateway ──► MCP client ──HTTPS──► the publisher's MCP server
"@plugin tool" in the composer ──────┘    (approval, logging, trimming)        (its own host, its own code)
```

1. The plugin is an entry in `plugins.json`: its URL, how to sign in, its hosts, its publisher, and whether it is free, paid with the SurfSense license, or paid on the publisher's own service ([`../core/02-registry.md`](../core/02-registry.md)).
2. The user connects it: egress consent for its hosts, then sign-in ([`01-mcp-client.md`](01-mcp-client.md)).
3. The gateway lists its tools and calls them for opencode, the chat engine's router step and `@` mentions ([`../core/01-architecture.md`](../core/01-architecture.md), [`../core/03-engines.md`](../core/03-engines.md)), asking for approval as the tool's annotations require ([`../core/04-trust.md`](../core/04-trust.md)).
4. The publisher's server does the work and answers. A paid SurfSense plugin's server checks the license on every call ([`../core/05-paid.md`](../core/05-paid.md)).

## Who hosts what

| Publisher | Code | Runs on |
|---|---|---|
| SurfSense | [`plugins/`](../../../../plugins/README.md), and `plugins/proprietary/` when paid | Its own containers, apart from `surfsense_backend` ([`02-surfsense-servers.md`](02-surfsense-servers.md)) |
| A partner or a community developer | Wherever they keep it | Their own server |
| A user's custom plugin | Wherever its publisher keeps it | Its publisher's server; it is in the user's app only, not in `plugins.json` |

A remote plugin needs the network and sends each call's arguments to its publisher, which the screen says before Connect. Offline plugins come with [bundles](../bundles/README.md).
