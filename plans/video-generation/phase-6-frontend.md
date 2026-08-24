# Phase 6 — Live deliverable job card and MP4 handoff

**Status:** DESIGN.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Depends on:** Phase 2b (generic job lifecycle/API), Phase 5 (ready Artifact and ranged MP4 serving), and `surfsense_web/`.

## 1. Goal

Render a generic live card as soon as interactive video execution returns its pending `DeliverableJob` receipt. The card follows the durable job through queued, running, cancelling, cancelled, failed, and ready states without requiring an Artifact to exist early.

When the job becomes ready and Zero publishes `artifact_id`, the card hands off to the exact existing MP4 artifact player/manifest/Range path. Do not add a second player or a job-specific media endpoint.

## 2. Zero lifecycle data

Publish a thin `deliverable_jobs` row and mirror the existing podcast/automation lifecycle subscription pattern:

- Add `zero/schema/deliverable-jobs.ts`, `zero/queries/deliverable-jobs.ts`, barrel registrations, and `hooks/use-deliverable-job-live.ts`.
- Expose only lifecycle-safe fields: `id`, `kind`, `title`, `status`, `phase`, `progress`, `failure_code`, nullable `artifact_id`, workspace/thread attribution, and timestamps.
- Never publish trusted request/checkpoint JSON, Celery task IDs, sandbox/workdir details, heartbeats, billing diagnostics, or `internal_error`.
- Apply existing `canReadSpace`/allowed-space constraints to by-space and by-id queries.
- Subscribe by stable job ID from the enqueue receipt. Retry preserves this same card/job identity.

The pending card is the pre-artifact UI. It must render correctly while `artifact_id` is null and must not query a media manifest until the job is ready.

## 3. Generic lifecycle card

Add a generic component under `components/tool-ui/deliverable-job` and register the video enqueue tool as a body tool in the assistant message/tool UI mappings.

- **Queued:** show that work is waiting for the video worker. With concurrency `1`, later jobs remain queued without being treated as stalled.
- **Running:** show trusted `phase` and bounded `progress` from Zero for narration, project preparation, preflight, still review, render, verify, and save.
- **Cancelling:** disable repeated cancellation and show a neutral cooperative-cancellation state.
- **Cancelled:** show client-owned copy and offer Retry.
- **Failed:** map stable `failure_code` values to sanitized copy and offer Retry when allowed.
- **Ready:** resolve `artifact_id` and hand off to the reusable existing video artifact card.

Unknown phases and failure codes use neutral fallback copy. Never render backend exception strings, tool output, or model-authored status text.

Merge generic in-flight jobs into the artifacts library using the existing podcast/video-run merge pattern. Keep podcasts on their current dedicated lifecycle for now. Do not expose queued generation in public threads without an explicit authentication, billing, and immutable-snapshot contract.

## 4. Cancel and Retry

Add a small authenticated API client following `PodcastsApiService`:

- **Cancel** is available for queued and running jobs until Artifact linking begins. A queued job may become cancelled without worker execution; a running job transitions to cancelling while the worker cooperatively stops.
- **Retry** is available for failed and cancelled jobs. It requeues the same job/card identity, increments attempts server-side, clears public failure state, and rechecks quota/policy.
- Disable controls while requests are pending, make repeat actions idempotent, and reconcile the result from Zero rather than inventing optimistic terminal states.
- Respect workspace RBAC/ownership failures and render sanitized client copy only.

The UI cannot cancel a ready job and never deletes an Artifact as a cancellation side effect.

## 5. Sanitized failure copy

Map stable codes locally, including:

- `duration_limit`: the video exceeds the three-minute limit.
- `quota_exceeded`: generation cannot continue under current quota.
- `generation_failed`: the authoring workflow could not complete.
- `render_failed`: rendering could not complete.
- `verification_failed`: the MP4 did not pass final checks.
- `cancelled`: generation was cancelled.

Do not display Celery, OpenSandbox, ffmpeg, Remotion, stack traces, provider responses, internal paths, or subagent timeout details. Log correlation belongs on the backend by job ID, not in the card or chat transcript.

## 6. Ready handoff to the existing MP4 path

Extract/reuse the ready MP4 card currently reached from `components/tool-ui/save-artifact.tsx` so both save results and ready jobs use one implementation:

- On `status="ready"` with `artifact_id`, load the existing artifact manifest and PRIMARY `video/mp4` `content_url`.
- Render the existing `Mp4VideoPlayer` with the same authenticated backend URL and HTTP Range behavior.
- Keep `controls`, `playsInline`, and `preload="none"` so no media request occurs before play.
- Preserve existing download and artifact-library behavior.
- Reuse the existing KB viewer registration for `video/mp4`; the job card adds lifecycle UI, not another artifact-viewing architecture.

Ready without `artifact_id` is an invalid server state and should show a neutral recoverable card error, not attempt playback.

Legacy audio/scene-code playback remains during rollout and is removed only in Phase 8.

## 7. Checks

- The enqueue receipt immediately renders a queued card before any Artifact exists.
- Zero updates exercise queued, each running phase/progress state, cancelling, cancelled, failed, and ready.
- Every stable failure code maps to safe copy; unknown codes are neutral; raw backend/internal errors never render.
- Cancel works for queued/running, is disabled once linking starts, and cancelled jobs never request artifact media.
- Retry preserves job/card identity and returns through queued/running states.
- Ready transitions to the existing artifact manifest/Range/`Mp4VideoPlayer` path and issues no media request before play.
- In-flight jobs merge into the artifact library without duplicate identity; workspace authorization applies to all subscriptions/actions.
- Existing MP4 seeking/download and legacy playback remain regression-covered.

## 8. Exit criteria

1. Users receive a live generic job card immediately after enqueue, before any Artifact exists.
2. Zero exposes only safe lifecycle data and the UI displays only client-mapped failure copy.
3. Cancel and explicit Retry follow the durable backend state machine while preserving card identity.
4. Ready jobs hand off to the existing MP4 artifact player and authenticated Range-serving path without duplicating media UI.
