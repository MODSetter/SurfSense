# Phase 7 — Legacy video migration and backfill

**Status:** DESIGN. Not implemented.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Depends on:** Production validation of Phases 1–6.

## 1. Goal

Convert every legacy video Artifact that currently stores narration plus browser-rendered scene source into a verified MP4 PRIMARY file without requiring the user to regenerate it.

This is a server-side sandbox re-render, not a transcode. Legacy scene source is untrusted code and must never be executed in the browser after migration. The backfill must execute that source only inside the network-disabled sandbox, then reuse structural verification, streaming persistence, and the durable `DeliverableJob` lifecycle.

Phase 7 does not exist in the current codebase. In particular:

- there is no `backfill_video_mp4.py`;
- the existing `backfill_video_artifacts.py` performs the historical `VideoPresentationRun` to Artifact migration and must not be confused with MP4 re-rendering;
- the current live video executor accepts an authored-video request, not a legacy-source backfill intent;
- no legacy compatibility adapter or migration ledger has been implemented.

## 2. Locked migration contract

The implementation must:

1. inventory every legacy video Artifact and its scene source, narration, and metadata;
2. create a new verified MP4 generation on the **same Artifact identity**;
3. execute historical scene code only inside an isolated, network-disabled sandbox;
4. support historical injected globals through a versioned compatibility runtime, without regex source mutation;
5. preserve legacy inputs only for migration retry and rollback—not for continued client execution;
6. keep the current Artifact PRIMARY unchanged until the replacement MP4 is verified and committed;
7. reconcile the current separate Artifact-save/job-ready commits before production backfill;
8. block Phase 8 while any legacy video still requires browser execution of stored scene code.

The live deterministic authoring prompt must not be used to rewrite historical content. Backfill needs a trusted adapter and explicit executor entrypoint.

## 3. Proposed control plane

Add a separately named one-time script only after the design above is approved. It should:

- support dry-run inventory without database writes;
- classify already-MP4, ready-to-backfill, and blocked candidates;
- create at most one versioned idempotent `DeliverableJob` per source Artifact in apply mode;
- dispatch the existing generic `deliverables.execute_queued` task;
- enqueue bounded batches;
- report database outcomes without polling Celery internals or rendering in the script process.

The private job request may add a versioned trusted backfill intent and source Artifact ID. No public backfill schema, video-specific lifecycle table, or second Celery task is required.

Backfill should use the current shared `surfsense` Celery worker and existing backend/Celery image unless production measurements lead to a separately approved queue change. It must not assume a `video_render` queue.

## 4. Proposed deterministic execution

A backfill-capable executor would:

1. claim the generic job and create the normal attempt-owned sandbox/workdir;
2. stream stored legacy audio into `public/`;
3. adapt stored scene source into typed harness input without regex source mutation;
4. run native preflight and supported still review;
5. render the final MP4;
6. run the existing structural verification and signed-receipt checks;
7. stream the verified MP4 through generic Artifact storage;
8. record a terminal migration outcome and preserve the original data through the rollback window.

It must retain attempt-scoped task IDs, sandbox ownership, cancellation, retry, failure sanitization, and cleanup from the live job system.

## 5. Outcomes and remediation

Every source Artifact has a tracked migration state:

- **Backfilled:** a verified MP4 became the approved PRIMARY generation.
- **Already migrated:** a valid MP4 PRIMARY already existed.
- **Blocked:** required data is missing or compatibility/render/verification has not yet succeeded.

Blocked is not an acceptable final state for Phase 7. It requires operator remediation, a corrected compatibility adapter, restored inputs, or an approved server-side conversion/export path. The system must not solve a blocked migration by continuing to execute stored scene code in the client.

## 6. Safety and operations

- Use a versioned source-Artifact identity so reruns cannot duplicate jobs or billing.
- Recheck current PRIMARY state after claim to close enumeration races.
- Preserve original audio and scene metadata through validation and rollback, then remove client dependency on them after migration is accepted.
- Pause bounded enqueue batches if migration work harms interactive latency.
- Keep compatibility diagnostics private; reports expose IDs, timestamps, terminal category, and stable failure code.
- Prove cancellation and failed attempts leave the original PRIMARY unchanged.
- Account explicitly for the current Artifact-save/job-ready transactional gap before production backfill.

## 7. Exit criteria

1. Dry-run inventory classifies the full legacy population.
2. Representative real artifacts pass the compatibility adapter, verification, save, and playback flow.
3. Duplicate enumeration and duplicate task publication create no duplicate job, blob, Artifact generation, or billing.
4. Every legacy video is Backfilled or Already migrated; no Blocked item remains.
5. Every migrated Artifact plays from its verified MP4 and never executes stored scene code in the client.
6. Original legacy inputs remain available only through the production validation and rollback window.
7. Phase 8 receives proof that the browser renderer and stored scene-code playback path are no longer required.
