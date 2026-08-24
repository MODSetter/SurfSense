# Phase 5 — Worker-owned persistence and MP4 serving

**Status:** DESIGN.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Depends on:** Phase 2b (queued deliverable jobs), Phase 4 (signed video verification), and existing artifact storage/serving.

## 1. Goal

Persist a verified MP4 as the PRIMARY artifact file through the existing generic artifact spine, then serve it with HTTP Range support. Persistence is the final operation of the queued worker workflow; the interactive turn only creates a `DeliverableJob` and returns its pending receipt.

The ordering invariant is:

`DeliverableJob → queued/running work → verified MP4 → streamed save → Artifact link + ready`

There is never a placeholder Artifact. Queued, running, cancelling, failed, and cancelled jobs have `artifact_id = null`.

## 2. Atomic save contract

Reuse `deliverables/tools/save_artifact.py` from the existing deliverables subagent in trusted queued-job mode. Do not add a second video recorder or a worker-only persistence model.

1. Recheck that the job is running, not cancelling, has no linked artifact, and owns the sandbox/workdir.
2. Validate the signed verification receipt against the final MP4 path and canonical `format="video"`.
3. Stream the MP4 from the sandbox into storage while calculating SHA-256 and byte count in one pass; never buffer the full MP4 in backend memory.
4. Reject and delete the uploaded blob if the stream hash differs from the receipt.
5. Create the `Artifact`/PRIMARY `ArtifactFile`, link `job.artifact_id`, and transition the job to `ready` in one database transaction.
6. If storage succeeds but the database transaction fails, perform compensating blob cleanup. If cleanup itself fails, record/log a cleanup incident without converting the job to ready.

The job must be durable before broker dispatch and long before artifact creation. `ready` and non-null `artifact_id` become visible together; clients must never observe a ready job without its Artifact or an Artifact belonging to a non-ready job.

## 3. Streaming storage

Add the minimum format-neutral streaming primitives needed by the existing artifact service:

- `StorageBackend.put_stream(key, chunks, *, content_type)`: Azure passes the async iterable to `upload_blob`; local storage writes chunks to one open file.
- A streaming artifact-file save path reads the job-owned sandbox MP4 in chunks, updates SHA-256 and byte count, and writes the PRIMARY blob.
- Populate `ArtifactFile.size_bytes` from the streamed count and compare the final digest with the Phase-4 receipt.
- Persist the artifact format explicitly from `verification.format`, producing `format="video"` rather than deriving `"mp4"` from the suffix.
- Keep document byte-based persistence unchanged; do not build a broader streaming abstraction than this path requires.

No blob produced during rendering, narration, previews, or verification is an Artifact file. Those files remain temporary in the isolated job sandbox.

## 4. Failure, cancellation, and retry

- Check cancellation before storage upload and immediately before the linking transaction. Once Artifact linking begins, cancellation is rejected.
- A cancelled job stops before save and leaves no Artifact row or retained PRIMARY blob.
- A save, hash, quota, verification, or database failure leaves the job failed with `artifact_id = null` and no retained PRIMARY blob.
- Map failures at the job boundary to stable public codes such as `quota_exceeded`, `verification_failed`, or `generation_failed`; storage/provider/Celery/stack details remain internal.
- Explicit Retry requeues the same job identity, increments attempts, rechecks quota/policy, and starts with no Artifact/blob from the failed attempt.
- Automatic retries are only for typed transient failures and remain safe through deterministic task IDs, atomic worker claim, and the idempotent save/link checks.
- Worker cleanup always terminates the job-owned sandbox in `finally`; a cleanup failure cannot overwrite a committed ready/failed/cancelled lifecycle state.

## 5. Serving

Extend the existing authenticated artifact content path; do not add a video-specific read route:

- Parse single open-ended and closed byte ranges and return `206 Partial Content`, correct inclusive `Content-Range`, `Accept-Ranges: bytes`, MIME `video/mp4`, existing ETag, and immutable cache headers.
- Return `200` for a full request and `416` for an unsatisfiable range. Multipart byte ranges remain out of scope.
- Add `StorageBackend.open_range(key, start, end)` (Azure ranged download; local seek/read) through the existing artifact-file service.
- Permit inline serving for `video/mp4`; retain workspace RBAC on every request.
- Downloads continue through the existing PRIMARY-file download path.

Legacy writers, routes, and per-slide audio remain in this phase for rollout/backfill compatibility and are removed only by Phase 8.

## 6. Checks

- Enqueue creates a job and no Artifact; queued/running/cancelling states keep `artifact_id = null`.
- A verified fixture streams to local and Azure storage without a full MP4 buffer; size and SHA-256 match the receipt.
- Artifact creation, job linkage, and ready transition commit atomically.
- Hash mismatch, failed verification, cancellation, upload failure, and database failure leave no Artifact and no retained PRIMARY blob; storage-success/database-failure exercises compensating cleanup.
- Duplicate delivery cannot create a second Artifact or blob.
- `Range: bytes=0-1023` returns correct `206`; full GET returns `200`; an invalid range returns `416`; seeking works on every backend.
- Public lifecycle data contains no internal storage, sandbox, Celery, or stack-trace text.

## 7. Exit criteria

1. The durable job always precedes the Artifact, and only successful worker verification/save creates and links one.
2. Failed and cancelled attempts retain neither an Artifact row nor a PRIMARY blob.
3. A ready job points to one canonical `format="video"` MP4 artifact saved through the generic streaming path.
4. Existing authenticated manifest, download, and ranged content routes serve the MP4 to the existing frontend player.
