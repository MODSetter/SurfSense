# ADR 0054: SurfSense's own plugins, free and paid, run on one plugin host that also serves the registry

- **Status:** Proposed, with the [plugins proposal](../proposals/plugins/README.md)
- **Date:** 2026-10-10
- **Supersedes:** [ADR 0047](0047-premium-plugins-are-source-available.md) in part: paid plugins living in `plugins/proprietary/`, each a container of its own
- **Source:** design discussion, 10 Oct 2026 (no permalink)

## Context

SurfSense publishes its plugins as remote MCP servers and hosts them itself ([ADR 0051](0051-plugins-are-mcp-servers-behind-one-tool-gateway.md)). ADR 0047 gave each paid plugin its own container. The backend already runs every scraper in one image with Xvfb and the browsers, and a container per plugin would multiply images, deployments and routing for plugins that are mostly small. The registry also needs a host ([ADR 0053](0053-plugins-are-listed-in-a-registry-and-third-party-ones-start-off.md)), and the license key must reach only one.

## Decision

- One container, the plugin host, deployed to Azure Container Apps at `plugins.surfsense.com`, runs every SurfSense plugin, free and paid, each at `/<id>/mcp`, and serves the signed registry. It is apart from `surfsense_backend` and imports none of its code.
- Its code lives in `plugins/remote/`: the host, the server kit every plugin builds on, free plugins under Apache-2.0, and paid plugins in `plugins/remote/proprietary/` under the Business Source License 1.1. The registry stays in `plugins/registry/`, since it lists bundles too.
- The folder decides a plugin's license; the registry's `access` decides its price.

## Consequences

- One image and one deploy ship every plugin. A crash or a heavy load in one plugin can affect the others, so each plugin turns its own errors into MCP errors and runs every call under a deadline.
- Every plugin's secrets are in the one container. Each reads only its own settings section; that is acceptable only because every plugin on the host is SurfSense's own.
- `plugins.surfsense.com` is the one host for the registry, for SurfSense's plugins and for the license key, so one consent covers all three.
- Without `plugins/remote/proprietary/`, the host builds and serves only the Apache-2.0 plugins.
- The root `LICENSE` line ADR 0047 requires names `plugins/remote/proprietary/`.

## Where the code stands

- No plugin host, `plugins/remote/` or `plugins/registry/` exists. The earlier design's tooling is in `plugins/bundles/`.
