# Frontend — Phase 1: Shell

> Owns: `surfsense_local/frontend/`. API contract: FastAPI **`/openapi.json`** ([`../api/01-skeleton.md`](../api/01-skeleton.md)).
> Copy from: `surfsense_web/` (strip Next/Zero/auth).

## Goal

App opens with model selection, then navigation and workspace screens.

## Work

- **First screen: local generation model selection.**
  - Load `GET /llm/providers` and the existing
    `GET /llm/selection/generation`; a selection `404` means not configured,
    not a broken API.
  - For each healthy provider, load
    `GET /llm/providers/{provider}/models` and show only installed models with
    the `completion` capability. Do not hardcode Ollama or model names.
  - A manual Refresh checks provider health and reloads installed models, so a
    model pulled outside SurfSense appears without restarting the app.
  - Refresh preserves the draft choice while it remains available. If the
    chosen or persisted model disappeared, clear the draft and show a stale
    selection warning; never silently choose another model.
  - Save explicitly through `PUT /llm/selection/generation`. The API rechecks
    installation and role compatibility at write time; the frontend list is
    guidance, not the trust boundary.
  - Cover initial loading, API unavailable, provider unavailable, no compatible
    models, refreshing, saving, save failure, and saved states. A failed save
    keeps the user's draft so it can be retried.
- Vite + React + router + Tailwind/shadcn.
- Layout: sidebar, workspace switcher, routes Documents / Chat / Studio / Settings.
- Workspace list + create → `GET/POST /workspaces`.
- Switcher entries rename (`PATCH /workspaces/{id}`) and delete
  (`DELETE /workspaces/{id}`). Deleting takes every document in it, so confirm first.
- Deep link to a workspace → `GET /workspaces/{id}`; unknown id is a 404 page,
  not an empty shell.
- Placeholder pages for unfinished features.

## Frontend structure

Keep the feature local until a second screen needs shared client state:

```text
src/
├── App.tsx
├── features/model-selection/
│   ├── api.ts
│   ├── use-model-selection.ts
│   ├── model-selection-page.tsx
│   └── model-selection.test.tsx
├── components/ui/             # shadcn primitives only
└── lib/api.ts                 # shared JSON request/error handling
```

- `App.tsx` is composition only.
- `features/model-selection/api.ts` owns exact HTTP contracts.
- `use-model-selection.ts` owns load, refresh, draft, and save transitions.
- `model-selection-page.tsx` owns accessible presentation and event wiring.
- Model identity is `(provider, name)`, never the model name alone.
- No global store, router data layer, React Query/SWR, or Electron API is needed
  for this screen.

Use shadcn Card, Alert, RadioGroup, Badge, Button, Skeleton, and Spinner
composition with the repository's semantic color tokens. The model choices
must support keyboard navigation and visible focus; status and errors must be
available to assistive technology. Keep the primary action disabled until a
compatible model is selected and while a save is in flight.

Model download/catalog UI remains Phase 5. With no compatible installed model,
this screen explains how to install one and offers Refresh; it does not start a
pull.

## Acceptance

- Fresh data directory: compatible installed models appear; choosing one saves
  it and a refresh restores it.
- Pull a compatible model outside the app, press Refresh, and the new model
  appears without restart.
- An embedding-only model is not offered for generation.
- Stop Ollama: the screen reports the provider unavailable and Retry/Refresh
  recovers after Ollama starts.
- Remove the current model: Refresh reports the stale selection and requires an
  explicit replacement.
- Keyboard-only selection and save work in light and dark themes and at a
  narrow desktop window width.
- Dev: create workspace, refresh, still listed.
- Rename shows the new name without a reload; delete removes it from the switcher.
- Runs in browser against local API.

## Needs from API

Workspace routes — [`../api/01-skeleton.md`](../api/01-skeleton.md). Model
provider inventory and validated generation selection —
[`../api/03-chat.md`](../api/03-chat.md).
