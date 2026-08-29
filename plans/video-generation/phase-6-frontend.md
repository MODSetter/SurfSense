# Phase 6 — Live deliverable job card and MP4 handoff

**Status:** IMPLEMENTED.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Depends on:** Phase 2b, Phase 5, and `surfsense_web/`.

## 1. Outcome

The pending enqueue receipt immediately renders a live video-generation card. The card follows the durable job through Zero and hands ready output to the existing MP4 Artifact UI.

```text
enqueue receipt {job_id, title}
  → Zero byId subscription
  → lifecycle card
  → ready artifact_id
  → Mp4ArtifactCard
  → manifest + native video player + download
```

No Artifact is required for the queued/running UI, and no job-specific media path exists.

## 2. Zero contract

Backend publication and migration 187 expose a safe `deliverable_jobs` projection. The frontend mirrors it in:

- `zero/schema/deliverable-jobs.ts`;
- `zero/queries/deliverable-jobs.ts`;
- schema/query barrel registrations;
- `hooks/use-deliverable-job-live.ts`.

Published fields are ID, kind, title, status, phase, progress, failure code, nullable Artifact ID, workspace/thread attribution, and create/update timestamps.

Private request/checkpoint JSON, task ID, attempt count, cancellation/heartbeat/claim internals, sandbox data, billing, and `internal_error` are not published. Queries use existing allowed-space authorization and subscribe by stable job ID.

## 3. Chat card

`components/tool-ui/deliverable-job.tsx` provides the generic lifecycle component and `assistant-message.tsx` registers `enqueue_deliverable_job`.

The fixed-height, full-width card uses the same video icon and color treatment across non-ready states:

```text
tool starting  → Starting video generation
queued         → Generating your video                     [Cancel]
running        → safe phase label / Generating your video [Cancel]
cancelling     → Cancelling video generation
cancelled      → Video generation was cancelled           [Retry]
failed         → mapped safe failure message              [Retry]
ready          → existing MP4 Artifact card
```

The card intentionally does not render a progress bar or percentage. `progress` remains available in Zero for lifecycle consumers, while visible running copy comes from a safe phase-label map. Unknown phases and failure codes use neutral fallback text.

Card height, status-line height, title truncation, and fixed action width prevent vertical or horizontal shifts across states and mobile widths. Action labels remain “Cancel” and “Retry” while pending; the controls are disabled without replacing their text.

## 4. Cancel and Retry

`deliverable-jobs-api.service.ts` sends workspace/job-specific POST requests:

```text
/api/v1/workspaces/{workspace_id}/deliverable-jobs/{job_id}/cancel
/api/v1/workspaces/{workspace_id}/deliverable-jobs/{job_id}/retry
```

- web uses a relative same-origin URL through the Next API proxy;
- desktop uses the configured backend URL and bearer token;
- controls disable while the request is pending;
- the UI does not invent optimistic terminal states;
- Zero supplies the authoritative resulting state;
- queued/running can cancel;
- failed/cancelled can retry;
- ready has no lifecycle action.

The backend GET route exists for authenticated clients and diagnostics, but the web card does not use a GET client because Zero is its live source.

## 5. Failure copy

The client maps:

- `duration_limit`
- `quota_exceeded`
- `generation_failed`
- `render_failed`
- `verification_failed`
- `cancelled`

Messages are user-facing and contain no Celery, queue, worker, OpenSandbox, Remotion, ffmpeg, provider, internal path, stack trace, or timeout detail.

## 6. Ready handoff

On `ready` with `artifact_id`, the component renders the shared `Mp4ArtifactCard` from `save-artifact.tsx`.

That path:

1. loads the generic Artifact manifest;
2. selects the PRIMARY `video/mp4` file;
3. passes its authenticated content URL to `Mp4VideoPlayer`;
4. preserves controls, `playsInline`, and `preload="none"`;
5. uses existing HTTP Range behavior and download action.

Ready without an Artifact ID displays a neutral unavailable state rather than attempting playback.

## 7. Artifacts library and other surfaces

`use-library-deliverable-jobs.ts` merges only queued, running, and cancelling video jobs into the artifacts library. Ready jobs come from the normal Artifact list. Failed/cancelled jobs are currently omitted.

The chat artifact sidebar does not treat a pending `job_id` receipt as an Artifact. Public threads do not expose queued video generation. Existing KB MP4 viewer registration reuses the same player.

## 8. Implemented coverage

Unit coverage verifies:

- enqueue bootstrap and Zero-missing/loading behavior;
- every lifecycle state and safe fallback;
- no rendered percentage/progress bar;
- stable card dimensions and action widths;
- safe phase/failure text;
- job-specific Cancel/Retry paths and web/desktop routing;
- pending-action disabled behavior;
- ready handoff to `Mp4ArtifactCard`;
- native MP4 player lazy loading.

Dedicated tests for the artifacts-library merge and the live hook are not currently present.

## 9. Acceptance

- the pending card appears before any Artifact;
- safe Zero data drives every lifecycle state;
- Cancel/Retry target only their exact job and reconcile from the backend;
- UI text never exposes infrastructure;
- non-ready layout remains stable across states and widths;
- ready output uses one shared MP4 manifest/player/download architecture.
