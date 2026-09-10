# API — Phase 4: Studio

> Owns: `modules/artifacts/`. Schema: [`../00c-data-model.md`](../00c-data-model.md)
> (`artifacts`, `artifact_files`), [ADR-0003](../../../docs/adr/0003-artifacts-as-documents.md).

## Goal

Accept a Studio job, expose the resulting artifacts, and stream their files —
through **one service entry** that both the REST job (v1) and a future
`create_artifact` chat tool call. Explicit now, agentic later, same code.

## Work

- **`service.py::create_artifact_job(workspace_id, format, document_ids, prompt,
  options, *, tool_call_id=None)`** — the hybrid seam. Validates `format` against
  the buildable set and checks any required model role, creates the `ARTIFACT`
  `Document` (`status=pending`) and its `artifacts` sidecar (`generation=1`,
  provenance from `tool_call_id`), enqueues `studio_job.delay(artifact_id)`,
  returns the artifact. The REST route passes no `tool_call_id`; the tool passes
  its own. Nothing else differs between the two triggers.
- **`router.py`**:

  | Method | Path | Does |
  |---|---|---|
  | `GET` | `/workspaces/{id}/studio/formats` | buildable formats + availability from selected model roles; the picker renders from this |
  | `POST` | `/workspaces/{id}/studio/jobs` | `{format, document_ids, prompt?, options?}` → 201 artifact |
  | `GET` | `/workspaces/{id}/artifacts` | list (status read from each artifact's `ARTIFACT` document) |
  | `GET` | `/artifacts/{id}` | detail + `files[]` |
  | `GET` | `/artifacts/{id}/manifest` | title, markdown body, `files[]` with `content_url` — the viewer's contract |
  | `GET` | `/artifacts/{id}/files/{role}` | stream `primary` \| `preview`; `Range` support for podcast audio |
  | `DELETE` | `/artifacts/{id}` | delete the document → sidecar + blobs cascade |

- **Read-only body (ADR obligation 2).** `PATCH .../documents/{doc}` already
  refuses `content` edits when `document_type != NOTE`; the artifact rename/delete
  paths stay open, content does not.
- **Register the task** in `shared/queue.import_tasks()` so the API can enqueue
  what the worker consumes.
- **Freshness.** The worker notifies `POST /internal/events` on each status
  change; reuse the `documents` event keyed by the artifact's `document_id` (the
  body *is* a document) so the client's existing invalidation applies — no new
  channel unless the UI needs artifact-level payload.

## Format catalog

`formats` is computed, not stored: the buildable set is the worker's `BUILDERS`
registry. `image` is available only when `SelectedModel(IMAGE_GENERATION)`
resolves to a configured OpenAI-compatible connection. `infographic` is a
deterministic builder and needs only the generation role. The frontend never
hard-codes the list or checks secrets. Connection and role resolution are
defined in [`05b-openai-compatible-connections.md`](05b-openai-compatible-connections.md).
Each format response carries `requires_role` (`generation`,
`image_generation`, or null), `available`, and nullable `unavailable_reason`.
The legacy `requires_key` field is removed.

## Acceptance

- `POST .../studio/jobs` → 201 with an id; polling `GET /artifacts/{id}` flips to
  `ready` with downloadable files once the worker finishes.
- Image with no valid image-generation selection → a clear 409, not a queued
  job that is certain to fail.
- Infographic remains available with any valid generation selection; it does
  not require an image endpoint.
- Deleting an artifact removes the document, sidecar and blobs; a cleared chat
  thread leaves its artifacts intact (`chat_thread_id` set null).

## Interface to worker

Enqueues `studio_job(artifact_id)` — [`../worker/04-studio.md`](../worker/04-studio.md).
