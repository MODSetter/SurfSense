# ADR 0016: The app sends no telemetry or crash reports

- **Status:** Accepted
- **Date:** 2026-09-08
- **Source:** [Pivot plan L29](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L29), [Pivot plan L32](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L32), [Pivot plan L52](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L52)

## Context

SurfSense is positioned as an airgapped, open-source alternative to NotebookLM. The app's policy is that every outbound call needs the user's consent ([ADR 0017](0017-egress-off-by-default.md)). What the app does reach is described in [egress](../architecture/egress.md).

## Decision

No telemetry and no crash reporting in the app. Support runs on logs the user sends.

## Consequences

- The maintainers learn about usage and crashes only from what users report and the logs they choose to send.
- The app's code and its declared dependencies include no analytics or crash-reporting SDK, and Electron's `crashReporter` is never started. The one match for "telemetry" in `surfsense_local/` is `@opentelemetry/api`, listed in the frontend lockfile as an optional peer dependency of vitest and not installed.
- The egress list has no analytics destination, so there is nothing of the kind for a user to switch off.
- The per-license usage counts the business needs are to be kept by the hosted scraper API once license mode exists, for instrumentation only, never by the app ([contract 2](../contracts/02-scraper-api-auth.md)).
