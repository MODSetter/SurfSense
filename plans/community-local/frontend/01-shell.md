# Frontend — Phase 1: Shell

> Owns: `surfsense_local/frontend/`. API contract: FastAPI **`/openapi.json`** ([`../api/01-skeleton.md`](../api/01-skeleton.md)).
> Copy from: `surfsense_web/` (strip Next/Zero/auth).

## Goal

App opens with navigation and workspace screens.

## Work

- Vite + React + router + Tailwind/shadcn.
- API base URL: read `window.surfsense.apiUrl` (exposed by the Electron preload;
  falls back to `http://127.0.0.1:8000` in a bare browser). Electron picks the
  port in the packaged app, so do not hard-code it.
- Data fetching: TanStack Query client (freshness decision in [`../00-umbrella-plan.md`](../00-umbrella-plan.md)).
- Layout: sidebar, workspace switcher, routes Documents / Chat / Studio / Settings.
- Workspace list + create → `GET/POST /workspaces`.
- Switcher entries rename (`PATCH /workspaces/{id}`) and delete
  (`DELETE /workspaces/{id}`). Deleting takes every document in it, so confirm first.
- Deep link to a workspace → `GET /workspaces/{id}`; unknown id is a 404 page,
  not an empty shell.
- Placeholder pages for unfinished features.

## Acceptance

- Dev: create workspace, refresh, still listed.
- Rename shows the new name without a reload; delete removes it from the switcher.
- Runs in browser against local API.

## Needs from API

Workspace routes — [`../api/01-skeleton.md`](../api/01-skeleton.md).
