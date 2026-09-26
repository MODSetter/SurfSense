# ADR 0009: The UI stays fresh by invalidating queries on server-sent events, with no sync engine

- **Status:** Accepted
- **Date:** 2026-09-05
- **Source:** [Umbrella plan L115](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00-umbrella-plan.md#L115)

## Context

Zero gave the hosted web app two things: sync between clients and reactive queries. The desktop app has one user and one database file, so there is nothing to sync between clients, but the UI still has to react when a row changes. Those changes happen in the worker, a separate process from the API that serves the UI. The pieces are described in [the overview](../architecture/overview.md).

## Decision

- The client keeps server state in TanStack Query.
- On each status change the worker POSTs a small notice to `POST /internal/events` ([`worker/notify.py`](../../surfsense_local/backend/worker/notify.py)).
- The API fans it out on `GET /workspaces/{id}/events` as a named SSE event, `documents` or `artifacts`, carrying the changed row ids and their status, never the rows ([`modules/events/`](../../surfsense_local/backend/modules/events/)).
- The client invalidates the matching queries (`queryClient.invalidateQueries`) and refetches them.
- Polling with `refetchInterval` is the fallback.
- No WebSockets, no sync engine and no local replica.

## Consequences

- The API stays the only source of truth. The client refetches instead of merging.
- A dropped notice costs the client its live update until the next poll, never the job and never a Huey retry.
- `POST /internal/events` is unauthenticated. It relies on the API binding `127.0.0.1` ([ADR 0004](0004-desktop-app-is-its-own-tree.md)).

## Where the code stands

- The backend half ships: the SSE route, the internal notice route and the worker's notices.
- The frontend never subscribes. There is no `EventSource` anywhere in `surfsense_local/frontend/src`. [`features/sources/use-sources.ts`](../../surfsense_local/frontend/src/features/sources/use-sources.ts) and [`features/studio/use-studio.ts`](../../surfsense_local/frontend/src/features/studio/use-studio.ts) poll their lists every 1.5 seconds while an ingest or a Studio job is running, in their own loops rather than through TanStack Query.
