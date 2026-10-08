# ADR 0047: SurfSense's paid plugins are source-available under the Business Source License and unlocked by the SurfSense license

- **Status:** Accepted
- **Date:** 2026-10-04
- **Supersedes:** [ADR 0025](0025-scraper-client-as-paid-plugin.md) in part: paid plugin source living in `plugins/` under Apache-2.0
- **Source:** [file-agent README L252](https://github.com/MODSetter/SurfSense/blob/2327494854e590f484bd61e3b5ff9d1fc4db70ce/docs/proposals/file-agent/README.md#L252), [file-agent strategy L171–187](https://github.com/MODSetter/SurfSense/blob/2327494854e590f484bd61e3b5ff9d1fc4db70ce/plans/community-local/file-agent-strategy.md#L171-L187), maintainer decision, 8 Oct 2026 (no permalink)

## Context

ADR 0025 put paid plugin source in `plugins/` under Apache-2.0. Anyone could fork it and remove the app's license check, which is local and offline ([ADR 0019](0019-offline-licenses.md)). The license sells paid plugins, priority support and Enterprise controls, and nothing in `surfsense_local/` is gated, so that a fork has nothing to remove; the license's code has to sit outside the Apache-2.0 tree.

Plugins became MCP servers, remote ones first, hosted by their publishers ([ADR 0051](0051-plugins-are-mcp-servers-behind-one-tool-gateway.md)). For SurfSense's own paid plugins the publisher is SurfSense, and what they sell, such as the scrapers behind the scraper API, already runs on SurfSense's servers.

## Decision

- SurfSense's paid plugins are servers whose code lives in `plugins/proprietary/` under the Business Source License 1.1. The engines they front stay where they are; the scrapers stay in `surfsense_backend/app/proprietary/`, also under the Business Source License.
- A paid plugin is unlocked by the SurfSense license key, a trial included. The app sends the key only to SurfSense's own plugin hosts, and the server checks it on every call ([contract 2](../contracts/02-scraper-api-auth.md)).
- The first kind of paid plugin is remote: SurfSense hosts its server, and the user connects to it. A paid plugin that runs on the user's machine comes later, delivered by the license server only to a valid license, never in the installer or the public plugin list.
- Other publishers' paid plugins never use the SurfSense license. They charge on their own service and check access themselves.
- Everything else stays Apache-2.0: SurfSense's free plugins in `plugins/`, the app, its engines, the format skills, all job content, and job packs.

## Consequences

- The root [`LICENSE`](../../LICENSE) names only `surfsense_backend/app/proprietary/` as Business Source License today. It needs a line for `plugins/proprietary/`, with a copy of that license in the folder, before code lands there.
- Anyone can read a paid plugin's source, but production use outside the license's grant is not allowed. For a remote paid plugin the server's license check is the real gate.
- `surfsense_backend` keeps the license server and the engines paid plugins front; their servers live in `plugins/proprietary/`.

## Where the code stands

- No paid plugin, `plugins/proprietary/` folder or license line for it exists. License mode on the scraper API, which the scraper plugin needs, is not built.
- `surfsense_mcp` exposes the scrapers to outside clients with personal keys; it is not the app's plugin.
