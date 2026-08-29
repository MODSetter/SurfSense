# Phase 5 — Worker-owned persistence and MP4 serving

**Status:** IMPLEMENTED WITH A TRANSACTIONAL HARDENING GAP.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Depends on:** Phase 2b, Phase 4, and existing artifact storage/serving.

## 1. Outcome

A successfully verified MP4 is streamed from the attempt sandbox into the generic Artifact platform and served through the existing authenticated manifest, content, download, and HTTP Range routes.

```text
DeliverableJob
  → queued/running pipeline
  → verified MP4 + signed receipt
  → streamed PRIMARY ArtifactFile
  → Artifact ID
  → job ready
```

There is no job-specific media endpoint or second video storage model.

## 2. Save path

`execute_video_deliverable()` calls `save_artifact()` directly with:

```text
ArtifactFileStreamInput
  chunks = sandbox.read_file_stream(output_path)
  filename = generated .mp4 name
  mime_type = video/mp4
  expected_sha256 = verification receipt digest
```

Before save, the executor checks that the receipt path and canonical `format="video"` match the exact final output.

`store_artifact_file_stream()`:

- consumes the async byte stream without buffering the whole MP4;
- calculates byte count and SHA-256 while writing;
- uses the generic local or Azure streaming backend;
- rejects a final digest mismatch;
- deletes the uploaded blob when streaming or database persistence fails within the artifact service.

The saved file is the PRIMARY file and the Artifact format is explicitly `video`.

## 3. Current transaction boundary

The earlier design required Artifact creation, `job.artifact_id`, and `job.status=ready` in one transaction. That is not the current implementation:

1. `save_artifact()` creates and commits the Artifact and PRIMARY blob;
2. the Celery task separately calls `complete_deliverable_job(artifact_id=...)`;
3. that transition commits `artifact_id`, `ready`, progress 100, and finish time.

This creates a small failure window in which an Artifact can exist while the job has not reached ready. The database still prevents a ready job without an Artifact ID, but it does not guarantee the reverse.

Future hardening must either make the final linkage atomic or add explicit reconciliation/compensation for a successful Artifact save followed by job-completion failure. The specs must not claim that this is already transactional.

## 4. Cancellation, retries, and revisions

- Stage heartbeats and the parallel watcher prevent a cancelled/superseded attempt from normally reaching save.
- Cancel is not allowed for ready/failed/cancelled jobs.
- Explicit Retry starts a new attempt with a clean attempt sandbox and no linked artifact on the job.
- Transient provider retry requeues the current job safely through conditional state changes.
- Revision save supplies `expected_generation` for optimistic concurrency against the target Artifact.
- Sandbox cleanup remains independent from storage cleanup and cannot overwrite the lifecycle state.

## 5. Serving

The existing Artifact routes provide:

- manifest lookup with the PRIMARY `video/mp4` content URL;
- full `200` responses;
- single closed/open-ended byte ranges with `206 Partial Content`;
- correct inclusive `Content-Range` and `Accept-Ranges: bytes`;
- `416` for unsatisfiable ranges;
- ETag handling;
- inline MP4 disposition;
- workspace authorization;
- existing PRIMARY-file download.

Local storage seeks and reads the requested range. Azure uses ranged blob download. Multipart ranges remain out of scope.

The browser's native `<video>` element therefore seeks through the same generic artifact route used by all MP4 viewers.

## 6. Temporary and legacy data

Narration, generated scene source, stills, segments, receipts, and intermediate outputs remain temporary in the attempt sandbox. Only the verified MP4 becomes an Artifact file.

Legacy per-slide audio, scene metadata, old writers, and compatibility readers remain until the Phase-7 migration decision and Phase-8 retirement gates are complete.

## 7. Acceptance

- verified bytes stream to local/Azure-compatible storage without a full backend buffer;
- stored size and SHA-256 match the verification receipt;
- digest mismatch removes the partial blob and fails the attempt;
- the final Artifact uses canonical format `video` and MIME `video/mp4`;
- manifest, download, full content, `206`, `416`, ETag, and seeking use existing routes;
- no placeholder Artifact is created at enqueue;
- the separate Artifact-save and job-ready commits are tracked as an explicit remaining gap.
