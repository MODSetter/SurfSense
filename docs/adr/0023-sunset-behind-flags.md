# ADR 0023: Every hosted sunset behaviour sits behind a runtime flag, and nothing is deleted or redirected unconditionally

- **Status:** Accepted
- **Date:** 2026-09-14
- **Supersedes:** the web flag `NEXT_PUBLIC_SUNSET_MODE` in [Pivot plan L31](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L31), [Pivot plan L71](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L71) and [Pivot plan L246](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L246)
- **Source:** [Pivot plan L31](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L31), [Pivot plan L71–72](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L71-L72), [Pivot plan L76](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L76), [Pivot plan L249](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L249)

## Context

The hosted stack is also the open-source Docker self-host stack: `surfsense_backend`, `surfsense_web` and compose stay public and community-supported. Sunsetting the hosted service has to leave every self-hosted install behaving exactly as before. The wind-down as built is in [sunset](../architecture/sunset.md).

## Decision

- Every sunset behaviour is behind a flag, and nothing is deleted or redirected unconditionally. Self-hosters never set the flags.
- Backend: `SUNSET_MODE` is read from the environment on every call, so flipping it needs no deploy. Since [PR #1815](https://github.com/MODSetter/SurfSense/pull/1815) it takes effect only when `DEPLOYMENT_MODE=cloud` is also set (`is_sunset_mode()` in [`surfsense_backend/app/sunset.py`](../../surfsense_backend/app/sunset.py)), so a stray `SUNSET_MODE=1` in a self-hosted `.env` does nothing. When it is on, write requests answer `410 Gone`. Still open are `/auth` apart from registration, the license routes, the Stripe webhook, PATs and the scraper routes. `GET /health` reports `sunset: true`. Production sets `DEPLOYMENT_MODE=cloud` (maintainer-confirmed, 22 Sep 2026).
- Web: [`surfsense_web/proxy.ts`](../../surfsense_web/proxy.ts) reads a runtime `SUNSET_MODE` on every request and redirects every non-public route to `/sunset`. It replaces the plan's `NEXT_PUBLIC_SUNSET_MODE`, which nothing reads: `NEXT_PUBLIC_*` values are inlined at build time, so flipping one would need a rebuild ([`surfsense_web/lib/sunset.ts`](../../surfsense_web/lib/sunset.ts)).
- Legacy desktop clients learn about the sunset from the backend, not from a release. v0.0.40 reads `sunset` from `GET /health` once at startup and, when it is true, loads the live `/sunset` page ([contract 4](../contracts/04-sunset-flag.md)).

## Consequences

- Rollback is turning the flags off; nothing is deleted before T+30.
- The hosted code is not archived. `surfsense_backend` and `surfsense_web` stay as the self-host stack and as the backend for licenses and the scraper API.
- The legacy app carries no sunset content of its own, so the portal can change without a legacy release.

## Where the code stands

- The web redirect is not gated on `DEPLOYMENT_MODE`. `shouldRedirectToSunset()` checks `SUNSET_MODE` alone, so a self-hosted web app with that variable set would send its app routes to `/sunset` even though its backend ignores the flag.
