# ADR 0025: The hosted scraper API client ships as a paid plugin whose source lives in this repo

- **Status:** Accepted
- **Date:** 2026-09-22
- **Supersedes:** the pivot plan's Plugins decisions ([Pivot plan L55–60](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L55-L60)), its private-repo decision ([Pivot plan L46](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L46)) and its T+7 client paragraph ([Pivot plan L239](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L239)); the plugin spec's network rule ([Plugin spec L31](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/plugins/00-umbrella.md#L31)) and trial rule ([Plugin spec L34](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/plugins/00-umbrella.md#L34))
- **Source:** maintainer decision, 22 Sep 2026 (no permalink)

## Context

The pivot plan scheduled the client for the hosted scraper API as a thin HTTP module inside the app, shipped as 2.1.0 a week after launch, and kept plugin code that carries real logic in a private BSL repo. A plugin system has since been designed ([plugins proposal](../proposals/plugins/README.md)): a plugin is a folder in this repo, installed on demand and run as its own process for one job, and a `paid` plugin runs only with an unexpired license. Under [contract 2](../contracts/02-scraper-api-auth.md) the scraper API enforces the license on the server, once license mode is built, so the client has nothing to hide.

## Decision

- The hosted scraper API client ships as a `paid` plugin on the plugin system, not as the in-app thin client the pivot plan scheduled for 2.1.0 at T+7.
- Paid plugin source lives in this repo under `plugins/`, Apache-2.0, because enforcement is server-side. This replaces the private BSL repo for plugin code.
- A trial license unlocks paid plugins for its term. This replaces the plugin spec's "A trial does not unlock it."
- Before a plugin's first run, the app asks egress consent for each host the plugin declares in `plugin.json` ([ADR 0017](0017-egress-off-by-default.md)). This replaces the plugin spec's "Settings → Network does not apply to them." The app still does not intercept plugin traffic, so the consent covers the declared hosts and does not enforce them.

## Consequences

- Nothing reaches users until both the plugin system and license mode on the scraper API exist.
- PATs are purged at T+30, on 18 Oct 2026, so scraper API and MCP users depend on license mode by then.
- Anyone can read or fork the client. The check that matters is the scraper API's, and it holds against a fork that strips the client ([ADR 0019](0019-offline-licenses.md)).
- The proposal's Open questions list what is still undecided, among them how a `paid` plugin receives the license key it sends, and how a pull request adding one of our reserved-id plugins passes the manifest checker.

## Where the code stands

- Neither half is built. `plugins/` and `surfsense_local/backend/modules/plugins/` do not exist, and neither the hosted backend nor `surfsense_mcp` accepts `Authorization: License <key>`.
