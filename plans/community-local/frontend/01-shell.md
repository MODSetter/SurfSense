# Frontend — Phase 1: Shell

> Owns: `surfsense_local/frontend/`. API contract: FastAPI **`/openapi.json`** ([`../api/01-skeleton.md`](../api/01-skeleton.md)).
> Copy from: `surfsense_web/` (strip Next/Zero/auth).

## Goal

App opens with navigation and workspace screens.

## Work

- Vite + React + router + Tailwind/shadcn.
- Layout: sidebar, workspace switcher, routes Documents / Chat / Studio / Settings.
- Workspace list + create → `GET/POST /workspaces`.
- Placeholder pages for unfinished features.

## Acceptance

- Dev: create workspace, refresh, still listed.
- Runs in browser against local API.

## Needs from API

Workspace routes — [`../api/01-skeleton.md`](../api/01-skeleton.md).
