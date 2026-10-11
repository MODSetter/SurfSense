# ADR 0054: SurfSense's own plugins, free and paid, run on one plugin host that also serves the registry

- **Status:** Proposed, with the [plugins proposal](../proposals/plugins/README.md)
- **Date:** 2026-10-10
- **Supersedes:** [ADR 0047](0047-premium-plugins-are-source-available.md) in part: paid plugins living in `plugins/proprietary/`, each a container of its own
- **Source:** design discussion, 10 Oct 2026 (no permalink)

## Context

SurfSense publishes its plugins as remote MCP servers and hosts them itself ([ADR 0051](0051-plugins-are-mcp-servers-behind-one-tool-gateway.md)). ADR 0047 gave each paid plugin its own container. The backend already runs every scraper in one image with Xvfb and the browsers, and a container per plugin would multiply images, deployments and routing for plugins that are mostly small. The registry also needs a host ([ADR 0053](0053-plugins-are-listed-in-a-registry-and-third-party-ones-start-off.md)), and the license key must reach only one.

## Decision

- One container, the plugin host, deployed to Azure Container Apps at `plugins.surfsense.com`, runs every SurfSense plugin, free and paid, each at `/<id>/mcp`, and serves the signed registry. It is apart from `surfsense_backend` and imports none of its code. It scales by copies of the whole container on concurrent requests: one container lends a quiet plugin's room to a busy one, where a container per plugin keeps each one's idle copy and spare room.
- The host serves MCP without sessions, so any copy answers any request. Since opencode cancels a call with a message no stateless copy can match, the app's Stop calls the host's cancel route with a token for the thread, and the host finds the call through Redis.
- A call that can run past three minutes is a job, queued by one tool and collected by another, and run in the background by the job runner in the same container. Azure's ingress ends a request after 240 seconds, and opencode calls tools without MCP tasks.
- Redis, with persistence, holds the host's jobs, rate limits, license state and caches, and Blob Storage holds jobs' results, which can be many megabytes. There is no database, since all of it expires within a day and is read by its key.
- Its code lives in `plugins/remote/`: the host, the server kit every plugin builds on, free plugins under Apache-2.0, and paid plugins in `plugins/remote/proprietary/` under the Business Source License 1.1. The registry of third-party plugins stays in `plugins/registry/`, since it lists bundles too.
- Each plugin is its own MCP server at its own path, with its own tools and its own entry in the first-party list; SurfSense's scrapers are one plugin per platform. One container serves every SurfSense plugin, free or licensed, today's and later ones, so adding one is a folder and a list entry. A plugin that must scale or fail apart runs from the same image in a container of its own, and one whose dependencies cannot share the image gets its own image; either is reached at its own path on `plugins.surfsense.com`, so the app sees no difference.
- A free plugin is open to anyone who reaches the host, not only SurfSense's users, so its requests are limited per IP address, as a licensed plugin's are per license.
- The folder decides a plugin's license; its entry's `access` decides its price.
- Only SurfSense's maintainers change `plugins/remote/proprietary/`. A pull request from anyone else that touches it fails its check, so SurfSense holds all of its copyright and can move any of it to Apache-2.0 without a contributor agreement.

## Consequences

- One image, one container and one deploy ship every plugin and their jobs. A spike in one plugin scales them all, which costs little, since a plugin uses almost nothing until it is called. A crash or a heavy load in one plugin can affect the others, so each plugin turns its own errors into MCP errors and runs every call under a deadline.
- Every plugin's secrets are in the one container. Each reads only its own settings section; that is acceptable only because every plugin on the host is SurfSense's own.
- `plugins.surfsense.com` is the one host for the registry, for SurfSense's plugins and for the license key, so one consent covers all three.
- Without `plugins/remote/proprietary/`, the host builds and serves only the Apache-2.0 plugins.
- The root `LICENSE` line ADR 0047 requires names `plugins/remote/proprietary/`.

## Where the code stands

- No plugin host or `plugins/registry/` exists. `plugins/remote/` holds only `proprietary/LICENSE`, which the root `LICENSE` names. The earlier design's tooling is in `plugins/bundles/`.
