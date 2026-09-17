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
  | `GET` | `/artifacts/{id}/files/{role}` | stream `primary` \| `preview`; `Range` support for podcast audio |
  | `DELETE` | `/artifacts/{id}` | delete the document → sidecar + blobs cascade |

  **As built, this table is both short and long.** `GET /artifacts/{id}/manifest`
  was never written: the viewer reads `GET /artifacts/{id}` plus the file stream
  instead, and `dependencies.py` still carries a comment referring to "the file
  and manifest routes". Decide whether the manifest is still wanted or the
  detail route is the viewer's contract, and make this table say so. Shipped
  alongside the rows above, and absent from them:

  | Method | Path | Does |
  |---|---|---|
  | `POST` | `/artifacts/{id}/regenerate` | re-run the job, bumping `generation` on the sidecar |
  | `POST` | `/artifacts/{id}/cancel` | stop a queued or running build (see the cancel note below) |
  | `PUT` | `/artifacts/{id}/quiz-state/{answer\|skip\|retake}` | quiz progress, persisted in `artifact_metadata` |
  | `PUT` | `/artifacts/{id}/flashcard-state/{mark\|reset\|order}` | flashcard progress, same storage |
  | `GET` | `/workspaces/{id}/studio/podcast/brief` | the brief the panel shows before a podcast job is submitted |

- **Cancel.** `POST /artifacts/{id}/cancel` and its ingest twin
  `POST /workspaces/{id}/documents/{id}/cancel` mark the backing document
  `cancelled` — a fifth `DocumentStatus`, added in revision `0011` — and call
  `revoke_pending()` on the owning Huey queue. A job already running is not
  killed: the worker calls `raise_if_cancelled()` between steps and unwinds on
  the next one. Cancelling something that is neither pending nor processing is a
  409.

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

`formats` is computed, not stored. As built the catalog is a declarative tuple in
[`modules/artifacts/formats.py`](../../../surfsense_local/backend/modules/artifacts/formats.py)
— twelve `Format` rows — and a unit test asserts the worker's `job_router.py`
names every key in it and nothing else, which is the same guarantee the
`BUILDERS` registry was meant to give.

Each row carries `requires_roles`, a **tuple** in the order the pipeline's
`render()` takes its models, not the single `requires_role` this spec first
described. Both `image` **and `infographic`** declare
`("image_generation", "generation")`, so both are unavailable without an image
selection; an earlier version of this section called `infographic` a
deterministic builder needing only the generation role, and that was never true
of the shipped pipeline. `podcast` additionally sets `requires_voice`, a flag
rather than a role because the bundled Kokoro voice is not selectable — it folds
into `requires_roles` if a `text_to_speech` role is ever added — and a
`validate_options` hook that checks the podcast brief. The frontend never
hard-codes the list or checks secrets. Connection and role resolution are
defined in [`05b-openai-compatible-connections.md`](05b-openai-compatible-connections.md);
note that an image selection can resolve to the bundled local `sdcpp` sd-server
as well as to a remote connection, so "needs an image role" does not imply "needs
a remote endpoint or a key". Each format response carries `available` and a
nullable `unavailable_reason`. The legacy `requires_key` field is removed.

## Acceptance

- `POST .../studio/jobs` → 201 with an id; polling `GET /artifacts/{id}` flips to
  `ready` with downloadable files once the worker finishes.
- Image **or infographic** with no valid image-generation selection → a clear
  409, not a queued job that is certain to fail. Both declare the same roles;
  neither is runnable on a generation model alone.
- Deleting an artifact removes the document, sidecar and blobs; a cleared chat
  thread leaves its artifacts intact (`chat_thread_id` set null).

## Interface to worker

Enqueues `studio_job(artifact_id)` — [`../worker/04-studio.md`](../worker/04-studio.md).
