# ADR 0047: SurfSense's paid plugins are source-available under the Business Source License and unlocked by the SurfSense license

- **Status:** Accepted
- **Date:** 2026-10-08
- **Supersedes:** [ADR 0025](0025-scraper-client-as-paid-plugin.md) in part: paid plugin source living in `plugins/` under Apache-2.0
- **Source:** [file-agent README L252](https://github.com/MODSetter/SurfSense/blob/2327494854e590f484bd61e3b5ff9d1fc4db70ce/docs/proposals/file-agent/README.md#L252), [file-agent strategy L171–187](https://github.com/MODSetter/SurfSense/blob/2327494854e590f484bd61e3b5ff9d1fc4db70ce/plans/community-local/file-agent-strategy.md#L171-L187), maintainer decision, 8 Oct 2026 (no permalink)

## Context

ADR 0025 kept paid plugin source in `plugins/` under Apache-2.0. A fork could remove any license check in the app ([ADR 0019](0019-offline-licenses.md)). Nothing in `surfsense_local/` is gated, so the code the license sells has to sit outside the Apache-2.0 tree.

Plugins became MCP servers, remote ones first, hosted by their publishers ([ADR 0051](0051-plugins-are-mcp-servers-behind-one-tool-gateway.md)). For SurfSense's own paid plugins the publisher is SurfSense, and what they sell, such as the scrapers behind the scraper API, already runs on SurfSense's servers.

## Decision

- SurfSense's paid plugins live in `plugins/proprietary/` under the Business Source License 1.1, each a container of its own that SurfSense deploys, holding everything it sells. Everything under `plugins/proprietary/` is under the Business Source License, including helpers that are Apache-2.0 in the backend today, such as the proxy, captcha and crawl code. All of it was written by SurfSense's maintainers, so SurfSense holds the rights to relicense it. The scrapers move there from `surfsense_backend/app/proprietary/`: copied now, and deleted from the backend once its scraper API no longer serves outside clients, never before the purge on 18 Oct 2026.
- A paid plugin is unlocked by the SurfSense license key, a trial included, checked by the plugin's server on every call and never by the app ([plugins proposal](../proposals/plugins/core/05-paid.md)).
- The first kind of paid plugin is remote: SurfSense hosts its server, and the user connects to it. A paid plugin that runs on the user's machine comes later, delivered by the license server only to a valid license, never in the installer or the public plugin list.
- Other publishers' paid plugins never use the SurfSense license. They charge on their own service and check access themselves.
- Everything else stays Apache-2.0: SurfSense's free plugins in `plugins/`, the app, its engines, the format skills, all job content, and job packs.

## Consequences

- The root [`LICENSE`](../../LICENSE) names only `surfsense_backend/app/proprietary/` as Business Source License today. It needs a line for `plugins/proprietary/`, with a copy of that license in the folder, before code lands there.
- Anyone can read a paid plugin's source, but production use outside the license's grant is not allowed. The server's license check is the only gate.
- Until the backend's copy is deleted, the scrapers exist twice, and a fix goes to both.

## Where the code stands

- No paid plugin, `plugins/proprietary/` folder or license line for it exists. The scrapers still live only in `surfsense_backend/app/proprietary/`.
- `surfsense_mcp` exposes the scrapers to outside clients with personal keys; it is not the app's plugin.
