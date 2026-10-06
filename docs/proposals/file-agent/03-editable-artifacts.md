---
status: proposed
code:
  - surfsense_local/backend/alembic/versions/
  - surfsense_local/backend/modules/artifacts/
  - surfsense_local/backend/modules/artifacts/local_image_demand.py
  - surfsense_local/backend/modules/llm/router.py
  - surfsense_local/backend/modules/documents/router.py
  - surfsense_local/backend/modules/chat/
  - surfsense_local/backend/modules/agent/tool_endpoint/
  - surfsense_local/backend/modules/agent/agent_threads/
  - surfsense_local/backend/shared/queue.py
  - surfsense_local/backend/worker/studio/job.py
  - surfsense_local/backend/worker/studio/revise_router.py
  - surfsense_local/backend/worker/studio/shared/
  - surfsense_local/backend/worker/jobs.py
  - surfsense_local/backend/worker/interrupted_documents.py
  - surfsense_local/backend/worker/consumer.py
  - surfsense_local/backend/worker/notify.py
  - surfsense_local/frontend/src/features/studio/
  - surfsense_local/frontend/src/features/studio/viewers/html-viewer.tsx
  - surfsense_local/frontend/src/features/studio/viewers/streamdown-config.ts
  - surfsense_local/frontend/src/features/chat/
  - surfsense_local/frontend/src/features/agent/
  - surfsense_local/electron/src/main/
---

# Editable artifacts

> An artifact becomes a list of versions that only grows. A regenerate, a refine prompt, an edit to a selected passage, an accepted tracked change, a restore, a workflow run and a file the agent wrote each make a new version, and every version is created by one function and run by a named job on the Studio or the engines queue. The version shown and indexed, the head, moves only when a run succeeds, so a failed or cancelled run never hides the last good output. Every edit names the version it was made against and is refused when the head has moved. A filled questionnaire or a redlined contract is an artifact derived from the user's file: its first version is that file with the edits applied as tracked changes, the user's file is never written, and the copy downloads without internal comments unless the user asks for them. Every edit returns a per-operation report built by the engine that applied it, not by the model, and an edit the user did not ask to be partial either applies whole or saves nothing.

**Status, 6 Oct 2026:** on `slice/revise`, a cut of the revised copies is built: `surfsense_revise_document` makes v1 of a revised copy from a ticked `.docx`, `.xlsx`, `.xlsm` or `.pptx` source and its next versions, with all-or-nothing reports, Word edits always tracked, internal comments, Accept all and Reject all as versions, and the "With changes" and "Clean" downloads under localized names. Versions stay artifacts with `version` in metadata, not `artifact_versions` rows; the engines run in the Studio worker, not an engines queue; quotes replace `inspect_document` ids. What is true now, and what was cut, is in [studio](../../architecture/studio.md#revised-copies) and its Known gaps.

Stream 03 of the file-agent proposal. Facts were checked against `dev_mod` at `0847e12f7` on 2026-10-03; "verified" means read in the linked file, "estimate" means not measured. Milestones (M0 to M10) are the [README](README.md)'s.

## Depends on

| Stream | What this design needs from it |
|---|---|
| [01 sources and folders](01-sources-and-folders.md) | Phase 0: the 50-source fix, the scope resolver in `modules/source_scope/` (`resolve_scope(…, exclude_document_ids=…)`), `gather()`'s budget, and the `VACUUM INTO` snapshot taken before `upgrade_to_head` applies a revision. Phase 3a: per-thread working folders (`thread_working_dir`), the thread-scoped tool URL `/agent/tools/workspaces/{ws}/threads/{thread}`, and `original_bytes.resolve_original` and `copy_original`, the only way an engine gets an original. Phase 5: the filing model that makes an artifact a source. |
| [02 skills and engines](02-skills-and-engines.md) | Licence-clean engines (docx apply with tracked changes, accept and reject, accept-all, `docx.external`, `docx.changes`; xlsx fill) that report `{code, values}` per operation and per `must_tell_user` line; `engines_queue`, `engine_job(version_id)` and its killable child, and `run_in_child()` for Studio versions that need an engine; `start_workflow()` and `workflow_job(version_id)`, whose run id is the version id; the agent tool list and its order; the spec builders that replace `exec()` for DOCX, PPTX, XLSX and PDF where they reach the `exec()` baseline. |
| [04 runtime and packs](04-runtime-and-packs.md) | Engines in the frozen worker (RT1); the WOFF2 fonts the DOCX viewer maps (RT2); Office support, the optional LibreOffice download (RT3b), for slide thumbnails, recalculated values (`recalc_copy()`) and PDF export (`convert()`). IronCalc values feed the xlsx diff and report only and never reach a file (04 decision 17). |
| [05 model ladder and evals](05-model-ladder-and-evals.md) | `capability_of(session)`: `formats`, `edit_rungs[format]` (this page's rungs 0 to 3), `engines` and `jobs`, which decide which edit entry points a model gets; `deferred_studio_jobs` and `release_deferred()`, which hold agent-started local Studio jobs until the turn ends; version rows as `edit_session` records. |
| [06 product shape](06-product-shape.md) | Where Refine (R1's refine thread), the chat Edit action, "Make a revised copy", review and Export sit; each item's verdict, "Not measured" included; the jobs that call `start_revised_copy` with a `job` key; "Regenerate with an instruction" as the only edit on a format without an edit rung; "Mark as reviewed". |

## Today

All verified.

- **One blob per role, no history.** `ArtifactFile` is unique on `(artifact_id, role)` and on `storage_key`; roles are `primary` and `preview` ([`models.py`](../../../surfsense_local/backend/modules/artifacts/models.py)). Files sit at `artifacts/<id>/<role>.<ext>` ([`persist.py`](../../../surfsense_local/backend/worker/studio/shared/persist.py)`::_write`), the same key on every run.
- **Regenerate destroys the previous output and takes no new prompt.** [`service.py`](../../../surfsense_local/backend/modules/artifacts/service.py)`::regenerate_artifact` refuses only a `pending` or `processing` document, so a failed artifact can be regenerated; it sets the document `pending`, increments `generation` and re-enqueues. The run's `persist._write_files` does `shutil.rmtree` on the folder and `artifact.files.clear()`; `_index` replaces every chunk.
- **A failed or cancelled regenerate hides a good output.** A row opens only when the document is `ready` ([`artifact-list.tsx`](../../../surfsense_local/frontend/src/features/studio/artifact-list.tsx)). Quiz and flashcard progress is keyed to `generation` ([`quiz_progress.py`](../../../surfsense_local/backend/modules/artifacts/quiz_progress.py)), so a failed run also resets it.
- **Disk and rows drift in two ways.** [`job.py`](../../../surfsense_local/backend/worker/studio/job.py)`::_generate` calls `persist.persist()` before `finish_job()`, and `finish_job` rolls back and returns `False` when a cancel won ([`worker/jobs.py`](../../../surfsense_local/backend/worker/jobs.py)). A cancel after persist leaves the new run's bytes at the old `storage_key` under the old row's `checksum_sha256`. A failure after the `rmtree` leaves rows that point at no file.
- **Pending Studio jobs survive a restart.** The queue is a `SqliteHuey` file ([`shared/queue.py`](../../../surfsense_local/backend/shared/queue.py)). [`interrupted_documents.py`](../../../surfsense_local/backend/worker/interrupted_documents.py)`::fail_interrupted_documents` fails only `processing` rows at worker start: "Pending ones are still queued and are left for this worker." `studio_job(artifact_id)` has `retries=1` ([`tasks.py`](../../../surfsense_local/backend/modules/artifacts/tasks.py)), and `_generate` re-raises after writing `failed`, so Huey runs it once more.
- **The Studio worker embeds.** `persist._index` chunks the body and calls `indexing.embed_passages` ([`persist.py`](../../../surfsense_local/backend/worker/studio/shared/persist.py)), so the Studio consumer already loads the embedding encoder. It runs four threads (`STUDIO_WORKERS = 4`, [`consumer.py`](../../../surfsense_local/backend/worker/consumer.py)). No task sets a Huey priority, though the installed huey 3.3.4's SQLite storage orders pending tasks by one (`task_priority_id` on `(priority desc, id asc)`).
- **"Studio is running" is read from the document's status in four places.** [`local_image_demand.py`](../../../surfsense_local/backend/modules/artifacts/local_image_demand.py) picks the sd-server type from `ARTIFACT` documents in `processing`; [`llm/router.py`](../../../surfsense_local/backend/modules/llm/router.py)`::_studio_running` blocks local model deletes only while one is `processing`; [`use-studio.ts`](../../../surfsense_local/frontend/src/features/studio/use-studio.ts)`::isRunning` keeps the 10-second poll while one is `pending` or `processing`; [`notify.py`](../../../surfsense_local/backend/worker/notify.py)`::notify_artifact_updates` sends the document's status.
- **Deletes check only the document's status.** [`documents/router.py`](../../../surfsense_local/backend/modules/documents/router.py)`::delete_document` deletes where status is not `processing`, then removes `artifacts/<id>/` after the commit; [`artifacts/router.py`](../../../surfsense_local/backend/modules/artifacts/router.py)`::delete_artifact` checks nothing.
- **No edit route.** Artifact routes are list, read, regenerate, cancel, file, quiz and flashcard state, delete. Document `PATCH` refuses content for anything but a `NOTE` (`documents/router.py::update_document`), [ADR 0003](../../adr/0003-artifacts-as-documents.md)'s obligation 2.
- **Half the formats keep nothing structured.** DOCX, PPTX, XLSX and PDF keep only a model-written script's output bytes, and their indexed body is the model's `summary` ([`office/pipeline.py`](../../../surfsense_local/backend/worker/studio/office/pipeline.py)). HTML's JSON is escaped into a fixed template and dropped ([`web/html/pipeline.py`](../../../surfsense_local/backend/worker/studio/web/html/pipeline.py)`::build`); the template holds no script.
- **Only flashcards and quiz ask for a schema.** They pass `json_schema=REPLY` to `generate.run_model`; mind map, html, image and infographic parse free JSON with `parse_json`; summary is markdown. Image and infographic take a painter and a writer, podcast a writer and a voice. The image spec's keys are `title` and `prompt` ([`image/pipeline.py`](../../../surfsense_local/backend/worker/studio/media/visual/image/pipeline.py)).
- **The HTML viewer runs scripts.** [`html-viewer.tsx`](../../../surfsense_local/frontend/src/features/studio/viewers/html-viewer.tsx) renders `srcDoc` in an iframe with `sandbox="allow-scripts allow-popups"`. Neither `frontend/` nor `electron/src/` sets a Content-Security-Policy, and Electron registers no `webRequest` filter. Chat's markdown blocks images with `allowedImagePrefixes: []` ([`message.tsx`](../../../surfsense_local/frontend/src/features/chat/message.tsx)); Studio's `streamdown-config.ts` does not. Formats without a viewer fall back to `DocumentViewer`, which prints the body as plain text.
- **Stale files can show.** Viewers fetch the unversioned `/artifacts/{id}/files/primary` ([`api.ts`](../../../surfsense_local/frontend/src/features/studio/api.ts)`::fileUrl`); the panel's `["artifact-panel", id]` query ([`artifact-panel.tsx`](../../../surfsense_local/frontend/src/features/studio/artifact-panel.tsx)) is never invalidated by `artifacts` events.
- **The agent cannot name what it made.** `surfsense_create_artifact` returns a sentence with no id ([`create_artifact.py`](../../../surfsense_local/backend/modules/agent/tool_endpoint/create_artifact.py)`::start`); files in `outputs/` are read by nothing ([agent](../../architecture/agent.md), Known gaps); nothing writes `artifacts.chat_thread_id`. `created_by_tool_call_id` and `updated_by_tool_call_id` exist on `artifacts`, but no caller passes `create_artifact_job`'s `tool_call_id`, so both are always null.
- **Chat history replays every stored message.** [`chat/router.py`](../../../surfsense_local/backend/modules/chat/router.py)`::_ground` selects all `ChatMessage` rows of the thread as history.
- **Downloads use Electron's default save dialog.** `downloadUrl` adds `?download=1`; `electron/src/` has no `will-download` handler or `showSaveDialog` call. The agent's file names pass [`mirror_path.py`](../../../surfsense_local/backend/modules/agent/thread_folder/mirror_path.py)`::file_name`'s filter, which replaces control characters and `<>:"/\|?*`, strips leading and trailing dots and spaces, keeps 100 characters and adds `_` to a Windows device name such as `CON` or `NUL`.
- **A table with a cascading child cannot be rebuilt by a migration.** [`shared/db.py`](../../../surfsense_local/backend/shared/db.py)`::_apply_pragmas` turns `foreign_keys` on for every connection and [`alembic/env.py`](../../../surfsense_local/backend/alembic/env.py) uses that engine. SQLite's `DROP TABLE` deletes rows first, firing `ON DELETE CASCADE` ([SQLite](https://www.sqlite.org/lang_droptable.html)), so a batch rebuild of `artifacts` would empty `artifact_files`. Nothing references `artifact_files`, so it can be rebuilt. [`0022_embedding_indexes.py`](../../../surfsense_local/backend/alembic/versions/0022_embedding_indexes.py) adds a referencing column with a raw `ALTER TABLE … ADD COLUMN … REFERENCES`. The latest revision is `0023`.
- **The agent proposal rules this out.** [Its README](../agent/README.md) lists "Editing sources or artifacts, undo, git history" as out of scope.

## Decisions

1. **Versions are rows in `artifact_versions`, and files belong to a version.** A version has its own status, base, inputs, report and provenance, which must be queryable; JSON history was rejected for ADR 0003's reasons. One artifact keeps one `ARTIFACT` document.
2. **The head moves only when a version is ready.** `artifacts.head_number` is the shown and indexed version; a pending, failed or cancelled version leaves it. Once a head exists, "is Studio running" is read from version rows, never from the document.
3. **Versions are append-only; restore makes a new version.** Restoring v2 under head v5 makes v6. Users lost work to restores that rewrote history ([v0](https://v0.app/docs/versions), E6).
4. **Every edit names its base; a stale base or a version in flight is a `409`.** A partial unique index allows one version in flight per artifact. ADR 0003 already named "an optimistic `generation` for later-turn revision".
5. **One version contract across streams.** `start_version()` creates every version, sets its `queue`, and dispatches it by kind to `studio_job`, `engine_job`, `workflow_job` or `version_job`; `begin_version()` and `finish_version()` are the guarded transitions in whichever worker runs it; `cancel_artifact()` and both delete routes reach every job.
6. **`generation` stays the last number handed out; progress keys on `head_number`.** No column changes meaning in place, and a failed run no longer resets a quiz.
7. **Only the head is indexed, and only the Studio worker embeds.** Versions keep title and body unchunked; moving the head re-chunks in the same transaction. ADR 0003's one body per document, and no drafts competing in search. Chunks and vectors for engine and agent versions are computed in the Studio worker, which already loads the encoder, so the engines worker stays lean.
8. **Files go in per-version folders; identical files within one artifact are hard-linked.** Restore and accept-all reproduce earlier files. Cross-artifact dedup waits for a measured need, because `artifact_files` has no index that would find a twin.
9. **Media keeps fewer old files.** Podcast, image and infographic keep files for the head and the two newest other ready versions; a 10-minute 24 kHz mono 16-bit WAV is about 29 MB (computed).
10. **`spec` exists only for builder-rendered versions; engine operations are stored as `plan`.** Refine rewrites a spec and a builder renders it, which keeps [ADR 0010](../../adr/0010-studio-builders-not-sandboxes.md). An engine-edited file has no spec and is never rebuilt from its ops.
11. **A revised copy of the user's file is a new artifact derived from it; v1 is the file with the edits applied; the file is never written.** The engine reads the original only through 01's `resolve_original` and `copy_original`. The B2B plan's "the edit is the product, delivered as a revised copy" ([`08-b2b-artifact-jobs.md`](../../../plans/community-local/seo/08-b2b-artifact-jobs.md)) and the agent proposal's "nothing edits the user's files".
12. **Engine edits are tracked changes, and nothing can turn tracking off.** docxkit writes only tracked changes, `edit_document` has no `tracked` argument, and the server never sets `allow_untracked_accept` (02 decision 7). So every docx edit of a source or of an artifact with `derived_from_document_id` set reaches the user as proposed changes; xlsx and pptx, which have no usable native tracking, keep each edit's history in `changes`. Spec-backed drafts the user made in Studio apply at once with a diff. Users objected when the two blurred ([Cursor forum](https://forum.cursor.com/t/bring-back-per-change-apply-inline-diff-review-you-re-throwing-away-your-best-ux-advantage/160856)).
13. **The apply report is 02's `apply-report/1`, stored as the engine wrote it.** Agent, chat, selection and plan edits are all-or-nothing: one failed operation fails the version and saves nothing. Only a workflow run with `partial=True` can be ready with failed operations. The interface renders each operation's and each `must_tell_user` line's `{code, values}` through the ICU catalogs, with the engine's English message as the fallback. Claude's artifact `update` returned OK when nothing matched ([#9434](https://github.com/anthropics/claude-code/issues/9434)); models drop what the build told them (I3, lesson 19).
14. **Agent outputs become versions only through an end-of-turn sweep of the thread's `outputs/`, confined to real files inside it.** Files written by bash or scripts produce no events (I1, I2). No tool copies an artifact into `outputs/` or publishes a path the model names.
15. **Artifacts become sources by stream 01's filing model.** Head only, never of themselves.
16. **A file artifact's indexed body is its text, not a summary.** An artifact used as a source must be found by what it says, and a body diff must mean something. Exec-made Office artifacts keep their summary while `exec()` makes them: until 02's builders replace it, and on a local model where a builder scores below the `exec()` baseline, which keeps `exec()` there (02 phase B).
17. **Export writes through a save dialog SurfSense controls, never into a linked root.** 01 keeps linked roots read-only. PDF export needs Office support.
18. **Internal comments never leave by default.** A revised copy's default download is 02's `docx.external`: comments with `audience: internal` removed and a leak scan in the report. "With changes (internal)" is an explicit second choice.
19. **Review is self-attested.** "Mark as reviewed" records the name the reviewer types and the time on that version. SurfSense is single-user with no accounts, so the interface and the docs call the record self-attested, and each new version starts unreviewed.

## Design

### The table and the migration

Revision `0024` (or the next free number; streams 01, 02 and 05 also add revisions), hand-written per [ADR 0005](../../adr/0005-hand-written-migrations.md) in `alembic/versions/0024_artifact_versions.py`. Before [`shared/migrations.py`](../../../surfsense_local/backend/shared/migrations.py)`::upgrade_to_head` applies it, 01 phase 0's `VACUUM INTO` snapshot is written to `<data>/backups/<from>-<to>.db` (the last two are kept), so a failed backfill can be restored from.

`artifact_versions`:

| Column | Notes |
|---|---|
| `id` | primary key |
| `artifact_id` | FK `artifacts.id ON DELETE CASCADE`; unique with `number` |
| `number` | `CHECK > 0` |
| `kind` | string, validated by `VersionKind` in code: `generate`, `regenerate`, `refine`, `edit`, `review`, `workflow`, `restore`, `copy`, `agent`, `legacy` |
| `status` | the `DocumentStatus` values, under a CHECK |
| `origin` | string, validated by `VersionOrigin`: `studio`, `chat`, `agent`, `viewer`, `workflow`, `upgrade` |
| `queue` | string, validated by `VersionQueue`: `studio` or `engines`; the worker that owns the version now (next section) |
| `base_number` | the version whose content was the input; null for `generate`, `regenerate`, `legacy`, an agent v1 and a derived v1 |
| `instructions` | at most 2,000 characters, as `StudioJobCreate.prompt` |
| `scope`, `inputs` | JSON: the selection inside the artifact; `{sources: [{document_id, version?}], source_scope?, grounded_document_ids?, prompt, options, base_sha256?, workflow?: {job}, output_sha256?}`, where `source_scope` and `grounded_document_ids` are 01's |
| `title`, `body` | the version's title and markdown body |
| `report`, `changes` | JSON: the apply report and the change summary |
| `model` | JSON `{provider, model, tier}`, null when no model wrote it |
| `chat_thread_id`, `step_ref` | FK `chat_threads.id ON DELETE SET NULL`; the opencode message and part |
| `approved_at`, `approved_by` | null until "Mark as reviewed"; `approved_by` is the name the reviewer typed |
| `error_message`, `created_at`, `started_at`, `finished_at` | `started_at` orders running jobs for `local_image_demand` |

`kind`, `origin` and `queue` are plain strings, as `artifacts.format` already is ([`models.py`](../../../surfsense_local/backend/modules/artifacts/models.py)), because `artifact_files` will reference `artifact_versions` with a cascade: like `artifacts`, `artifact_versions` can never be rebuilt to widen a CHECK. A partial unique index `artifact_versions_in_flight` on `(artifact_id) WHERE status IN ('pending', 'processing')` holds decision 4 in the database.

`artifacts` gains three nullable columns: `head_number`, `derived_from_document_id` (FK `documents.id ON DELETE SET NULL`) and `output_path`, with a partial unique index on `(chat_thread_id, output_path) WHERE output_path IS NOT NULL`. `output_path` is relative to that thread's `outputs/`, so the same name in two threads is two artifacts. The foreign key is added the way `0022` adds `documents.embedding_index_id`: `ALTER TABLE artifacts ADD COLUMN derived_from_document_id INTEGER CONSTRAINT fk_artifacts_derived_from_document_id_documents REFERENCES documents (id) ON DELETE SET NULL`. `test_migrations.py` proves the reflected key matches the model. `created_by_tool_call_id` and `updated_by_tool_call_id` stay, unwritten: the version's `step_ref` supersedes them, there is nothing to backfill, and dropping them is not worth a migration.

`artifact_files` is rebuilt with `op.batch_alter_table`: `version_id` (FK `artifact_versions.id ON DELETE CASCADE`, nullable, backfilled, then not null); unique `(artifact_id, role)` replaced by `(version_id, role)`; an index on `(artifact_id, checksum_sha256)` for hard-link lookups; the `role` CHECK gains `spec`, `plan`, `external` and `clean`. `storage_key` stays unique.

**Backfill, on evidence.** It runs per artifact that has no `artifact_versions` row, so a second pass inserts nothing; `test_migrations.py` runs it twice on a fixture database, and ADR 0005 requires that a second pass be a no-op. An artifact *has evidence* of a good output when its document has non-empty content, at least one chunk row exists for the document, and every `artifact_files` row names a file that exists and hashes to its `checksum_sha256` (summary-like formats have no file rows and pass on content and chunks). Hashing every artifact file at upgrade costs one read of the artifact store; on an SSD that is seconds for a gigabyte (estimate; measured on a large fixture before release).

| Document status | Evidence | Versions created | Head | Document afterwards |
|---|---|---|---|---|
| `ready` | yes | `v<generation>`, `ready`, kind `generate` (generation 1) or `regenerate`, inputs from `artifact_metadata`; owns the file rows | it | `ready` |
| `ready` | no | `v<generation>`, `failed`, "files missing or changed before the upgrade" | none | `failed` with that reason |
| `failed` or `cancelled` | yes, `generation > 1` | `v<generation - 1>`, kind `legacy`, `ready`, owning the file rows; `v<generation>` keeps the status and error | the legacy row | `ready`, error cleared |
| `failed` or `cancelled` | a file hash differs | `v<generation>`, `failed`, "an interrupted run replaced the file" | none | unchanged |
| `failed` or `cancelled` | otherwise | `v<generation>` with the status and error | none | unchanged |
| `pending` | yes, `generation > 1` | legacy `v<generation - 1>` as above; `v<generation>` `pending`, kind `regenerate` | the legacy row | `ready` |
| `pending` | otherwise | `v<generation>` `pending` | none | `pending` |
| `processing` | as `pending`, with status `processing` | as `pending` | as `pending` | as `pending` |

- A `legacy` version is "the output this artifact showed before versions existed". Its number is a free slot below `generation`, not a claim that run `generation - 1` made it: after ready, failed, failed, the output is generation 1's.
- File rows that fail the evidence test are deleted; their bytes stay under `artifacts/<id>/` until the artifact is deleted.
- Every backfilled version gets `queue = 'studio'`.
- A `pending` version is left for the queued job. `studio_job` gains a second argument (next section) with a default of `None`, which a queue entry written before the upgrade carries; `None` means "this artifact's in-flight version".
- A `processing` version is failed by `fail_interrupted_versions()` at Studio worker start, as `fail_interrupted_documents` fails only `processing` documents. The API migrates before workers start (`worker/consumer.py` runs `wait_for_schema()` first).

No file moves: legacy rows keep `artifacts/<id>/primary.<ext>`, and only new versions write into `v<n>/`. The delete unit stays `artifacts/<id>/`.

[`models.py`](../../../surfsense_local/backend/modules/artifacts/models.py) gains `ArtifactVersion`, `VersionKind`, `VersionOrigin`, `VersionQueue`, the four roles, `Artifact.versions` and `Artifact.head`. `Artifact.files` becomes the head's files, so `read_quiz_questions` and the file route keep working unchanged.

### Storage

`persist._write_files` becomes `persist.store_version_files(session, artifact, version, built)`. It writes into a fresh `artifacts/<id>/v<n>/`. For each blob it looks up an `ArtifactFile` of the same artifact with the same SHA-256 through the new index; when one exists on disk it calls `os.link`, falling back to writing bytes on `OSError` (exFAT, FAT32 and some network drives). Nothing is deleted, so the rows and files of every ready version agree whatever the commit does.

`persist.commit_version` is the one transaction that makes a version ready, and only the Studio worker calls it. Chunks and vectors are computed before it opens, so the write lock is held only for row writes ([`shared/db.py`](../../../surfsense_local/backend/shared/db.py)`::_begin`: "no transaction may stay open across a slow call"). Inside it:

1. It re-reads the artifact row. If the artifact was deleted, it rolls back and removes `v<n>/`.
2. It writes the version's title, body, report and changes, sets `head_number` and `generation`, replaces the document's chunks and content.
3. It sets the document's title only when the version is `generate` or `regenerate`, or when the document's title still equals the previous head's title. A rename the user made stands, as `finish_job` already promises ("a rename or a note edit committed meanwhile must stand").
4. It calls `finish_job` (v1) or `finish_version` (later), guarded against a cancel. If the cancel wins, nothing moved.

**Orphans.** `worker/studio/shared/retention.py::sweep_orphan_folders()` runs at Studio worker start, beside `fail_interrupted_versions()`. It removes `artifacts/<id>/` folders whose artifact row is gone, and `v<n>/` folders of versions that ended `failed` or `cancelled` and own no file rows. It never touches a version in flight.

**Download names** come from `modules/artifacts/download_names.py::download_name(artifact, version, role, suffix=None)` at serve time: `<title> v<n>.<ext>` for a Studio artifact, and `<source stem> (<suffix> v<n>).<ext>` for a revised copy. The suffix names the job and the file: "redline", "filled" or "revised" for the `external` file, the same with "internal" for `primary`, and "clean" for `clean`. Suffixes are interface text, and Electron main translates nothing ([ADR 0030](../../adr/0030-formatjs-renders-interface-text.md)), so the client renders the suffix through the ICU catalogs and passes it as `?suffix=`; English is the fallback when none is passed. Names pass `sources_folder.file_name`'s character filter, gain a leading `_` when the stem is a Windows device name (`CON`, `NUL`, `COM1` and the rest), and are capped at 255 bytes. `original_filename` stays as a record of what the pipeline or agent named the file.

### The version contract

`modules/artifacts/versions.py::start_version` is the only code that creates a version:

```python
def start_version(
    session: Session,
    artifact: Artifact,
    *,
    kind: VersionKind,
    origin: VersionOrigin,
    base_number: int | None,
    instructions: str | None = None,
    scope: dict | None = None,
    plan: dict | None = None,
    inputs: dict | None = None,
    chat_thread_id: int | None = None,
    queue: VersionQueue | None = None,
) -> ArtifactVersion:
    """Check the base, add the pending version, commit, then enqueue its job.

    Refuses with 409 when a version is already in flight, or when base_number
    is not the head: the caller edited a version someone else has replaced.
    """
```

It sets `queue` once at creation: `engines` for a `review`, and for an `edit` whose `plan` is complete at start; `studio` for everything else. A caller that passes a different `queue` gets a `ValueError`. Only the engines worker changes it afterwards, when it hands a finished engine run over to be indexed. It dispatches by kind:

| Kind, and how it starts | Job | `queue` | Why there |
|---|---|---|---|
| `generate`, `regenerate`, `refine`; an `edit` from a selection or chat Edit | `studio_job(artifact_id, version_id)` | `studio` | waits on a model; a file-backed edit runs its engine step through 02's `run_in_child()` |
| `workflow` | 02's `workflow_job(version_id)`, created by `start_workflow()`, which calls `start_version`; the run id is the version id | `studio` | waits on a model; its apply step runs through `run_in_child()` |
| an `edit` whose plan is complete at start (02's `edit_document`, a revised copy with a `plan`), `review` | 02's `engine_job(version_id)`, then `index_version(version_id)` | `engines`, then `studio` | a killable child and no model; the encoder stays in the Studio worker |
| `restore`, `copy`, `agent` | `modules/artifacts/tasks.py::version_job(version_id)` | `studio`, at a raised priority | no model; re-chunking needs the encoder |

**Indexing an engine version.** `engine_job` never chunks or embeds. When its child succeeds, one short transaction records the version's files in `v<n>/`, its report, plan, changes and views, sets `queue` to `studio` and the status back to `pending`, and then `modules/artifacts/tasks.py::index_version(version_id)` is enqueued. `index_version` runs `begin_version`, extracts the body with `accepted_text` (Agent outputs, below), computes chunks and vectors outside any transaction, and calls `commit_version`. A failed engine run never reaches it: `engine_job` calls `finish_version` with the report, and nothing was saved. A handed-over version is `pending`, so a Studio worker restart leaves it to its queue entry. The engines consumer imports only `modules.engine_runs.tasks` (02) and never loads the encoder.

**Priority.** `index_version` and `version_job` are enqueued with a raised Huey priority, so they run before queued Studio generations. They still wait while all four Studio threads are busy; 02's 25 s wait then tells the agent the version is still being made.

- **`begin_version(session, version) -> bool`** in `worker/jobs.py` is the guarded `pending → processing` update on the version row, plus `begin_job(document)` for v1, in whichever worker runs. It also allows `failed → processing` for Huey's retry, only when the version is still the artifact's highest number; the in-flight index refuses it if another version started meanwhile. A retry therefore re-runs its own version or nothing, never a newer one.
- **`finish_version(session, version, status, …) -> bool`** writes a terminal status unless a cancel won.
- **`cancel_artifact`** marks the in-flight version (and, for v1, the document) cancelled, then revokes queued entries with `shared/queue.py::revoke_where(queue, name, predicate)`: `studio_job` by its first argument; `engine_job`, `index_version`, `version_job` and `workflow_job` by `version_id`. A running engine child is stopped by `engine_job` itself, which polls the version and calls the plugin runner's `stop_process_tree` (02).
- **`fail_interrupted_versions(queue)`** in [`interrupted_documents.py`](../../../surfsense_local/backend/worker/interrupted_documents.py) fails `processing` versions whose `queue` is `studio` at Studio worker start and leaves `pending` ones to their queues; 02's `fail_interrupted_engine_runs()` does the same for `engines`.
- **`_generate` becomes `_run_version(session, artifact, version)`** in [`job.py`](../../../surfsense_local/backend/worker/studio/job.py): `generate` and `regenerate` call `job_router.pipeline_for(kind)` with the version's inputs; `refine` calls `revise_router.revision_for(kind)`; an `edit` with a scope asks the model for the replacement (Selection scopes) and, for a file-backed artifact, applies the server-built ops through `run_in_child()`. On a retryable failure it writes the reason on the version (and on the document for v1) and re-raises, as today.
- **Offline.** A version whose model becomes unreachable (a remote model without network, a stopped local runtime) fails with that reason when the call gives up. The head stays, and nothing resumes the version; the user starts the edit again. Engine runs need no network.

**Who reads "running".** All four readers move to version rows through `versions.py::running(session)`, versions in `processing` joined to their artifact's format and ordered by `started_at`:

- `local_image_demand` picks the oldest running image or infographic version, and measures its idle window from the last such version's `finished_at`;
- `llm/router.py::_studio_running` refuses a local model delete while any version is `processing`, v1 included;
- `notify_artifact_updates(artifact, version)` sends the version's status;
- `ArtifactRead` gains `pending_version`, and `use-studio.ts`'s `isRunning` also holds while it is set.

`ArtifactRead` also gains `head_number`, `last_failed_version` (`{number, kind, status, error_message}`), `derived_from` (`{document_id, title}`), `origin` and the head's `approved_at` and `approved_by`. `status` stays the document's, so a v1 in flight still reads `pending` and `use-studio.ts`'s toasts keep working.

**Delete.** `documents/router.py::delete_document`, `artifacts/router.py::delete_artifact` and 01's folder delete call `versions.guard_delete(session, artifact)`. A `processing` version answers `409` "Stop the running edit first"; a `pending` one is cancelled and revoked, and the delete goes on. With step 1 of `commit_version` and the orphan sweep, a deleted artifact leaves no bytes even when a worker loses the race.

### Regenerate, restore, retention

- **Regenerate.** `POST /artifacts/{id}/regenerate` takes an optional `{prompt?, source_scope?, base_number?}`. Without a body it makes a new version from the head's inputs, re-resolving `inputs.source_scope` through 01's resolver and falling back to `inputs.sources`; with one, those become the inputs. `render()` arity is unchanged. It refuses with `409` when v1's kind is not `generate` ("This was not made by Studio. Ask the agent or edit it instead."), replacing today's `KeyError` 500 on a non-catalog format.
- **Restore.** `POST /artifacts/{id}/versions/{n}/restore {base_number}` starts a `restore` version that copies body and spec and hard-links files. A version whose files were purged answers `409`.
- **Retention.** `retention.apply(session, artifact)` runs after each ready version. For podcast, image and infographic it unlinks the files of ready versions that are not the head and not among the two newest others, drops their file rows and records `files_purged` in the version's `inputs`. Rows are never deleted while the artifact lives. Pinning waits for phase 7.

### Specs and Refine

`Built` ([`artifact.py`](../../../surfsense_local/backend/worker/studio/shared/artifact.py)) gains `spec: dict | None`, stored as the `spec` role. Mind map keeps its JSON nodes, html `{title, sections}`, image `{title, prompt}`, infographic its brief, podcast its outline and turns; flashcards and quiz already keep theirs as `primary`; DOCX, PPTX, XLSX and PDF get one from stream 02's builders. Summary has no spec: its body is the markdown.

An artifact whose head has no `spec` role is file-backed: exec-made Office, an agent output, a revised copy, anything an engine edited. It can be regenerated (when Studio made it), edited by an engine or the agent, and restored; it is never refined at the spec level. Stream 02's engine operations are stored as the `plan` role and are never read as a spec.

`worker/studio/revise_router.py::revision_for(kind) -> Revise | None` sits beside `job_router`, so the router's equality and arity tests are untouched. A revisable pipeline adds `revise(*models, previous, instructions, sources) -> Built`, taking the same models in the same order as its `render()`: one writer for most formats, painter and writer for image and infographic, writer and voice for podcast.

- JSON formats return a whole new spec under the format's generation schema, and the existing `build()` renders it. Flashcards and quiz have that schema today. Mind map, html, image, infographic and the podcast outline get theirs from the small-model work in [05](05-model-ladder-and-evals.md) §7 and [`04-workflows.md`](../agent/04-workflows.md) decision 1; phase 2 writes any that have not landed.
- Summary refine is a markdown rewrite with no schema, checked only for "something changed".
- A podcast refine re-voices the whole episode and says so.
- Prompts live in `prompts/<tier>-revise.md`. Grounding is the base's sources, searched with the instructions, in `gather()`'s budget (01; 24,000 characters today) minus the spec's length, without the artifact itself. When spec plus minimal grounding exceeds the model's window ([`model_window.py`](../../../surfsense_local/backend/modules/agent/model_window.py)), the route answers `409`: "This is too long to refine with the selected model. Edit a part of it instead."

### Edit entry points

Each entry point sits on a rung of 05's `edit_rungs`. Rung 0 needs no model edit; rung 1 has the model write content for one spec or one scope, which the server applies; rung 2 is a multi-operation plan on a revised copy; rung 3 is an agent or a job thread.

| Rung | Entry | Route or tool | Model's work | Offered when ([05](05-model-ladder-and-evals.md)'s `capability_of(session)`) |
|---|---|---|---|---|
| 0 | Restore, accept or reject | routes below | none | always |
| 0 | Regenerate with a new prompt | `POST /artifacts/{id}/regenerate` | the format's generation | the format in `formats` is not `unavailable` |
| 1 | Refine box in the panel | `POST /artifacts/{id}/versions {kind: refine}` | rewrite a spec under its schema | `edit_rungs[format]` includes rung 1 |
| 1 | Selection edit in a viewer | `POST /artifacts/{id}/versions {kind: edit, scope}` | replacement text or values for one scope | `edit_rungs[format]` includes rung 1 for that scope kind |
| 1 | Chat Edit about an attached artifact | `MessageCreate.edit` | as Refine or a selection edit | as Refine or a selection edit |
| 2 | Instructions on a user's file or a revised copy | `revised-copies {job, instructions}` → `start_workflow` | the job's plan, in the workflow's shapes | `jobs[job]` at `workflow` or above |
| 3 | Agent | stream 02's engine tools, `revise_artifact`, the sweep | inspect, plan, iterate | `"agent" in capability.engines`, or `jobs[job]` at `job_thread` |

A format whose `edit_rungs` holds only rung 0 changes only by regeneration, and 06's card then offers "Regenerate with an instruction" alone. On an unmeasured model, 05's default offers rung 1 on summary, mind map, flashcards, quiz and html marked "Not measured", and the `refine_spec` and `selection_content` rows keep or remove it per model. Until 05 P4a lands in M4, the offer uses that unmeasured default as a fixed rule for every model (rung 1 on summary, mind map, flashcards, quiz and html, labelled "Not measured"), and from M4 it reads `capability_of(session).edit_rungs`.

**Chat.** A non-agent chat cannot reliably tell "explain this" from "change this", so intent is explicit. An attached artifact gives the composer two send actions, Ask and Edit. Edit sends `MessageCreate.edit = {artifact_id, base_number, scope?}` ([`chat/schemas.py`](../../../surfsense_local/backend/modules/chat/schemas.py)); `modules/chat/artifact_edit.py::start_edit_turn` calls `start_version(origin=chat, chat_thread_id=…)` and stores the reply as `content = {card: {artifact_id, version}}`, never as model text. The card follows `artifacts` events and shows the report. In history, `modules/chat/history.py::as_history(message)` renders a card from the version row's current state as one assistant line, for example `Made v4 of "MSA (revised)" from v3: 3 of 3 changes applied.` or `v4 of "MSA (revised)" failed: "30 days" is not in that paragraph.`; `_ground` uses it. In an agent thread the agent decides.

### Selection scopes

| Viewer | Scope | Resolved by |
|---|---|---|
| summary, mind map, html, docx | `{kind: "text-quote", exact, prefix, suffix}`, the W3C [TextQuoteSelector](https://www.w3.org/TR/annotation-model/#text-quote-selector) | the base body, or stream 02's docx outline, to a line or paragraph range; no match or several is a `409` "Select a little more text" |
| xlsx | `{kind: "cell-range", sheet, range}` | the workbook |
| pptx | `{kind: "slide", index}` | the deck |
| flashcards, quiz | `{kind: "item", index}` | the spec |

docx-preview puts no paragraph ids in the DOM (I5), so docx selections match by quoted text with context. The model writes only content, and the server builds the operations from stream 02's op set; no new op is needed:

- **Text quote, spec-backed:** replacement text, plain, capped at three times the selection's tokens. The server splices it into the spec or markdown and rebuilds.
- **Text quote, file-backed docx, inside one paragraph:** the same replacement text; the server issues one `replace` at that paragraph's `P:` id with `find` = the selected text.
- **Text quote, file-backed docx, across paragraphs:** the selection widens to whole paragraphs, and the panel shows the widened range before sending. The model writes an array of paragraphs; the server issues `add_paragraphs` after the last selected paragraph, then one `delete_paragraphs` from the first selected paragraph `through` the last, in one all-or-nothing apply, tracked as every engine write is.
- **Cell range:** a JSON array of rows whose schema fixes `minItems` and `maxItems` to the range's shape, written by the builder or stream 02's xlsx `set_cell` ops, which refuse formula cells unless asked.
- **Slide:** one slide's spec under the pptx builder's schema; spec-backed decks only until stream 02 has a pptx engine.

**Keyboard path.** Selecting with the mouse through `window.getSelection()` is not the only way in. The panel's outline lists the base's paragraphs (02's stored `views/outline.txt` for a file-backed docx, the body's paragraphs for a spec-backed format), and a revised copy's revision side list lists its changes. Arrow keys move, Space selects a paragraph, Shift extends the range, and "Edit selection" sends the same text-quote scope a mouse selection would, widened to whole paragraphs. The xlsx range and pptx slide selections built in phase 5 take arrow keys and Shift from the start.

### The apply report

`apply-report/1` is stored on the version, ready or failed, exactly as 02's `report.py::as_report(result)` writes it from its `EngineResult`; `worker/studio/shared/apply_report.py::from_engine` stores it as given, and `from_spec` writes the same shape for a spec edit. The fields are 02's: `schema`, `saved`, `ops` (`index`, `op`, `target`, `status`, `code`, `values`, `message`), `applied`, `failed`, `skipped`, `checks`, `must_tell_user`, `input_sha256` and `output_sha256`.

```json
{
  "schema": "apply-report/1",
  "saved": false,
  "input_sha256": "9f2c…",
  "output_sha256": null,
  "ops": [
    {"index": 0, "op": "replace", "target": "P:3A1F2B0C", "status": "skipped",
     "code": "BATCH_REFUSED", "values": {}, "message": "not applied because #1 failed"},
    {"index": 1, "op": "replace", "target": "P:44100D2E", "status": "failed",
     "code": "ANCHOR_NOT_FOUND", "values": {"find": "30 days"}, "message": "\"30 days\" is not in that paragraph"}
  ],
  "applied": 0, "failed": 1, "skipped": 1,
  "checks": [{"id": "only-targeted-text-changed", "ok": true}],
  "must_tell_user": []
}
```

- The engine or builder sets each `status`; the model's reply never does.
- **All-or-nothing by default.** Agent, chat, selection and plan edits call the engine with `partial=False`: any failed operation means `saved` is false, the version fails with "Nothing was saved: operation #1 failed; the other 1 was valid", the head does not move, and the report on the failed version says which operation to fix.
- **Partial only in workflows.** A workflow run with `partial=True` is `ready` with its failed and skipped operations listed, and the report card opens: "11 of 12 changes applied. 1 failed: …".
- Zero applied operations fails; so does a primary whose `output_sha256` equals the base's ("The edit changed nothing"); so does any failed check (an untracked change, a lost prior revision, a leak).
- **Rendering.** The panel's report card and the chat card render each `code` with its `values` through the ICU catalogs ([ADR 0029](../../adr/0029-icu-translation-catalogs.md), [0030](../../adr/0030-formatjs-renders-interface-text.md)); `message` is the English fallback for a code the catalog lacks, and is what the model reads. `must_tell_user` lines are always shown, rendered the same way, whatever the model says.
- A spec edit reports one operation, `spec`; its checks are schema validity and "something changed".

### Pending, proposed, applied, and diffs

Three states, never styled alike: **pending** is a version in flight ("Making v4 from v3…", with Cancel, head still open); **proposed** is a tracked change in a revised copy's head not yet decided ("12 changes to review"); **applied** is the head's content.

`changes` is computed at commit by `worker/studio/shared/changes.py::summarize`, read-only, with lxml, openpyxl (read-only mode; saving customer workbooks with it loses shapes, E5), python-pptx and pypdfium2.

| Format | Diff view |
|---|---|
| summary, mind map, html, flashcards, quiz, podcast script | line and word diff of body or spec from `GET …/compare/{b}`, computed with Python `difflib`, so no new frontend dependency |
| docx revised copy | the file with `renderChanges: true` and `renderComments: true`, plus a side list of revisions (author, date, text) from stream 02's `changes` that scrolls to each by text |
| docx Studio draft | a text diff of accepted-view bodies; a true docx-to-docx redline waits on a compare engine (Open questions) |
| xlsx | changed cells highlighted, a list `Sheet!A1: old → new` with formula changes marked; values recalculated by LibreOffice when Office support is installed, IronCalc's expected value shown in the diff only where 02 adopts it, otherwise marked "not recalculated" per formula ([04](04-runtime-and-packs.md) decision 17) |
| pptx | a changed badge per slide and a per-slide text diff; before and after thumbnails with Office support |
| pdf | per-page text diff |
| image, infographic | side by side |

docx-preview's change rendering is experimental; phase 4 checks it on the skills project's fixtures D01, D03 and D05 before shipping it on, with the revision list and clean copy as the fallback. `docx-viewer.tsx` also maps Calibri, Cambria, Arial and Times New Roman to the metric-compatible WOFF2 files that 04's RT2 ships, through `@font-face` with `local()` first. Diffs never rely on colour alone: insertions are underlined and deletions struck through.

**Accept and reject.** `POST /artifacts/{id}/revisions/decide {base_number, decisions: [{revision_id, action}] | all}` starts a `review` version on `engine_job`; stream 02's accept and reject run on the head, and the report lists each revision decided. No library in the app has per-revision controls in the rendered page (I5), so they live in the side list, which is keyboard-navigable.

### Revised copies of the user's files

`POST /workspaces/{ws}/documents/{doc}/revised-copies {job?, instructions?, plan?, label?}`, served by `modules/artifacts/revised_copies.py::start_revised_copy`:

1. Refuses unless the document is a `FILE` whose original has a format with an engine: docx first, then xlsx and pptx as stream 02 delivers.
2. Calls 01's `resolve_original(session, document)` in its transaction, so an online-only, missing or uncontained original is a `409` with 01's reason before any version exists, and records `inputs.base_sha256` as the document's `content_hash`.
3. Creates an `ARTIFACT` document titled `<source title> (revised)` and an artifact with `format` from the suffix and `derived_from_document_id = doc`.
4. With `job` and `instructions`, calls stream 02's `start_workflow(session, workspace, job, inputs)`, which creates v1 of kind `workflow` through `start_version` and records `inputs.workflow`. With `plan` (stream 02's engine tools and workflow steps), calls `start_version(kind=edit, plan=…)`, which puts it on the engines queue. Instructions with no workflow for that job and format answer `409` "No job handles this yet. Ask the agent instead."
5. The job resolves the original again in a short session and calls `copy_original(ref, destination)` into its scratch folder with no session open. Bytes that no longer match `content_hash` raise `OriginalChanged`: the version fails with its message, and `reconcile_requested_at` is set (01). The engine writes only into `v1/`. A test asserts the original's bytes and modification time are unchanged.

Every edit of a revised copy is tracked (decision 12). A docx version whose primary holds revisions or comments gets two more files in the same job, through the engine child: `external`, from 02's `docx.external` (comments with `audience: internal` removed, the leak scan in the report), and `clean`, accept-all applied to `external`. Download offers "With changes" (`external`, the default) and "Clean", and, as an explicit second choice behind a warning, "With changes (internal)" (`primary`). Those are the files regulated work expects (E6 §2.7), and an internal comment never leaves by default. Phase 4 does not ship without `docx.external`. Stream 02's `export_document` keeps `external` and `issues` for the agent and has no `clean`.

The panel says "Revised copy of MSA_Acme.docx" with a link; the source's row shows "2 revised copies". Deleting the source nulls `derived_from_document_id` and keeps the copy, whose docx still carries its tracked changes and whose xlsx history is in `changes`.

**Review.** `POST /artifacts/{id}/versions/{n}/approve {reviewer, write_properties?}` serves 06's "Mark as reviewed" and writes `approved_at` and `approved_by` on that version. `reviewer` is the name the user types at approval, prefilled with the workspace's `revision_author` (02). The interface and the docs call it self-attested, and a new version starts unreviewed. With `write_properties`, the route enqueues `reviewed_copy(version_id)` on the engines queue, which writes `Reviewed by` and `Reviewed on` into a copy's `docProps/custom.xml` under the version's `review/` folder; downloads of that version then serve the copy. The stored version files never change.

### Export

Download stays `GET …/versions/{n}/files/{role}?download=1`. `electron/src/main/downloads.ts` adds a `will-download` handler that shows the save dialog itself, asks the API for the workspace's linked roots, and refuses a destination inside one with "This folder is linked to SurfSense, which never writes into it. Choose another folder." The file then lands where the user chose, outside SurfSense's watch. PDF export of a DOCX or PPTX (phase 7) runs as `modules/artifacts/tasks.py::export_job(version_id, kind)` on the Studio queue, which calls 04's `worker/studio/shared/pdf_export.py::export_pdf(version_id, deadline)`; it converts a copy with 04's `soffice.py::convert()` outside `transact()`, under 04's app-wide conversion lock, and the download serves the result once. It is offered only when Office support is installed; without it, export offers the Office format only.

The workspace export and import bundle (README, M6) carries each artifact's versions: rows, `spec` and `plan` files, the files of versions that still have them, and `head_number`. Import keeps version numbers and the head, and re-chunks only heads.

### Agent outputs

This matters once a model has `agent` in `capability_of(session).engines` (05). Agent threads stay behind the developer switch until M5 turns the agent on in installers, which waits for this phase. The working folder is the thread's, from 01: `thread_working_dir(ws, thread)/outputs/`.

**What counts as a deliverable.** A file in `outputs/` or a subfolder, not under `_work/` or a dot-folder, not an Office lock file `~$*`, with suffix `.docx .xlsx .pptx .pdf .html .md .txt .csv .png .jpg .jpeg`, passing [`storage.py`](../../../surfsense_local/backend/modules/documents/storage.py)`::validate_upload`, non-empty and at most 100 MB. The agent prompt gains one line: finished files in `outputs/`, working files in `outputs/_work/` (the skills project's convention, I5).

**Confinement.** `modules/artifacts/output_files.py::real_deliverable(outputs_dir, path)` accepts a candidate only when:

- `os.path.realpath` of the candidate lies under the realpath of that thread's `outputs/`;
- `os.lstat` shows a regular file, not a symlink, and on Windows `st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT` is clear (junctions and other reparse points);
- `st_nlink == 1`, so a hard link to a file elsewhere is refused;
- after opening (with `O_NOFOLLOW` where the platform has it), `os.fstat` matches the `lstat`'s `st_dev` and `st_ino`.

Deleting an output file uses the same checks and `os.unlink` on the checked path, which does not follow links. Tests cover a symlink, a junction, a hard link to a file outside, a `..` path and a swap between check and open, on Windows and POSIX.

**The sweep.** `modules/artifacts/agent_outputs.py` runs in [`turn.py`](../../../surfsense_local/backend/modules/agent/agent_threads/turn.py)`::_stream` after the turn finishes and before `completed`, in two steps:

1. `scan(outputs_dir) -> list[Deliverable]`, in a thread off the event loop and outside any session: walk, confine, stat, hash (with an in-memory `(size, mtime_ns)` cache) and `validate_upload`. At most 50 new or changed deliverables per turn; the rest are listed in the frame as "not published: over 50 files this turn" or "over 100 MB".
2. `record(session, thread_id, deliverables)`, in one short `transact`: compare each hash with the head primary of the artifact whose `(chat_thread_id, output_path)` matches. Unchanged files are skipped. Changed ones call `start_version(kind=agent, base_number=head)`; new paths make a new artifact. Each records `inputs.output_sha256`.

`version_job` then copies the file into `v<n>/`, re-hashes the copy, and fails the version with "changed while publishing; it will be picked up next turn" on a mismatch. Because the sweep compares with stored heads, an aborted turn's files are swept next turn.

The sweep never creates a version of an artifact whose `derived_from_document_id` is set or whose v1 kind is `edit` or `workflow`; such artifacts have no `output_path`, and no tool copies them into `outputs/`. Agent changes to a customer's file go only through stream 02's engine tools, tracked.

**Bodies** come from `worker/studio/shared/body_text.py::accepted_text(format, path)` in `version_job` and `index_version`, both in the Studio worker: lxml for docx (skipping `w:del`), openpyxl read-only values for xlsx, python-pptx text per slide, pypdfium2 for pdf, `lxml.html` text for html, plain reads otherwise. No Docling: the body only has to be searchable, and running it on the ingest queue would split one version across two workers and two interrupted sweeps.

**Formats** come from the suffix: `docx`, `xlsx`, `pptx`, `pdf`, `html` and `image` use existing viewers. `.md` and `.txt` become `markdown` and `.csv` becomes `csv`, which are not in `FORMATS` (so the router equality test holds) and render through the registry's `DocumentViewer` fallback as plain text until phase 7's viewers.

**Untrusted HTML and markdown.** An agent-written page may carry script planted by a prompt injection in a document the agent read, and script in the renderer could send source text to any host outside `egress.require` ([ADR 0017](../../adr/0017-egress-off-by-default.md)). This hardening ships first, in M0, ahead of the rest of this phase, because the viewer runs scripts for every HTML artifact today. The html builder's template holds no script, so `html-viewer.tsx` drops scripts for every HTML artifact: `sandbox=""` (no `allow-scripts`, no `allow-popups`) and a `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'">` injected at the top of `srcDoc`, which also stops remote images. `streamdown-config.ts` gains `allowedImagePrefixes: []`, as chat's `message.tsx` sets, for every Studio viewer that renders markdown. A Vitest test renders an HTML artifact whose script sets a global and asserts it stays unset, and one whose `<img src="https://…">` makes no request.

**Provenance.** `chat_thread_id` comes from 01's thread-scoped tool URL for tool-started versions and from the turn for sweep versions; nothing guesses it. `step_ref` is filled after the turn by one function for both, `modules/artifacts/provenance.py::attach_steps(session, thread_id, messages)`, over the opencode messages `_stream` already fetches: a tool-started version matches the tool part whose input names its `artifact_id` or `source_id` and version; a sweep version matches the last `write` or `edit` part naming its path, or the assistant message for files bash wrote. Stream 02's "matched after the turn" bullet points here.

**Tools.** Stream 02 owns the list and its order. This stream needs:

- `create_artifact` (changed) returns `Studio started "Word" as artifact 12 v1 …` and records the thread.
- `revise_artifact {artifact_id, version, instructions}`, which 02 lists after `edit_document`. It calls `start_version(kind=refine, origin=agent)` for a spec-backed artifact and returns the version number, maps a `409` to a `ToolCallError`, and for a file-backed artifact answers "Use edit_document on this one." On the local runtime its Studio job waits in 05's `deferred_studio_jobs` until `release_deferred()` runs at the end of the turn, as 05 does for `create_artifact`, and the reply says the version will be made when the turn ends.
- Stream 02's `edit_document`, `compare_documents` and `export_document` land through `start_version` and `start_revised_copy`, so every agent edit gets the same base check and report.

**Frames and threads.** An `artifact-updated {artifact_id, number, status, title, report_summary}` frame goes out after the sweep and when a tool-started version finishes during the turn ([`turn_frames.py`](../../../surfsense_local/backend/modules/agent/agent_threads/turn_frames.py), [`sse.ts`](../../../surfsense_local/frontend/src/features/chat/sse.ts), `agent-steps.tsx`, [`step-label.tsx`](../../../surfsense_local/frontend/src/features/agent/step-label.tsx)). Deleting an artifact with an `output_path` deletes that file from the thread's `outputs/`, or the next sweep would publish it again. Deleting a thread nulls `output_path` on its artifacts and keeps them; 01 removes the folder, so no later sweep runs for it.

### Artifacts as sources

- Stream 01 decides how an artifact becomes a source: filed in a folder or ticked, and outside `all` while unfiled. This stream adds no Outputs group and no "include outputs" flag.
- Only heads are indexed, so a selected artifact is its head. `gather` records `inputs.sources[].version` for artifact sources, and the panel shows "a newer version of a source exists" when that head moves.
- `start_version` passes the artifact's own document as `exclude_document_ids` to 01's `resolve_scope`, so a refine never grounds on itself. A revised copy and its source selected together both stay, marked as a pair.
- The agent sees a filed artifact's head in 01's `sources/` mirror like any source, and edits artifacts it made through `inspect_document` and `edit_document` by id.

### Routes

| Method | Path | Does |
|---|---|---|
| `POST` | `/artifacts/{id}/regenerate` | optional `{prompt?, source_scope?, base_number?}`; a new version; `202` |
| `GET` | `/artifacts/{id}/versions` | versions, newest first, without bodies |
| `GET` | `/artifacts/{id}/versions/{n}` | title, body, files, report, changes, inputs, model, review |
| `POST` | `/artifacts/{id}/versions` | `{kind: refine \| edit, base_number, instructions?, scope?, plan?}`; `202`; `409` stale or busy |
| `POST` | `/artifacts/{id}/versions/{n}/restore` | `{base_number}`; `202` |
| `POST` | `/artifacts/{id}/versions/{n}/approve` | `{reviewer, write_properties?}`; the self-attested review |
| `GET` | `/artifacts/{id}/versions/{n}/files/{role}` | the file, `Cache-Control: private, max-age=31536000, immutable`; `?download=1&suffix=` names it |
| `GET` | `/artifacts/{id}/versions/{a}/compare/{b}` | body or spec diff and `changes` |
| `GET` | `/artifacts/{id}/versions/{n}/revisions` | a docx version's tracked changes |
| `POST` | `/artifacts/{id}/revisions/decide` | accept or reject; `202` |
| `POST` | `/artifacts/{id}/versions/{n}/exports` | `{kind: "pdf"}`; `202`; phase 7, with Office support |
| `POST` | `/workspaces/{ws}/documents/{doc}/revised-copies` | `201` |
| `GET` | `/workspaces/{ws}/source-roots/linked-paths` | for the export guard; from 01's `source_roots` |
| `GET` | `/artifacts/{id}/files/{role}` | kept as the head's file, now `Cache-Control: no-cache` |

They live in `modules/artifacts/version_router.py`. Quiz and flashcard routes pass `head_number` where they pass `generation`.

### Client changes

- [`api.ts`](../../../surfsense_local/frontend/src/features/studio/api.ts): `ArtifactVersion`, the new fields, a request per route; `fileUrl` and `downloadUrl` take the version, so viewers fetch immutable URLs, and `downloadUrl` takes the localized suffix.
- [`use-studio.ts`](../../../surfsense_local/frontend/src/features/studio/use-studio.ts): `isRunning` also holds while `pending_version` is set.
- [`artifact-panel.tsx`](../../../surfsense_local/frontend/src/features/studio/artifact-panel.tsx): keys `["artifact", id]` and `["artifact", id, "version", n]`; an `artifacts` event invalidates the `["artifact", id]` prefix (the hook gives no ids, so one refetch per open panel per event); a version switcher in the header actions; a bar on older versions, "Viewing v2 · Restore as v6"; a Changes toggle, the Refine box (spec-backed heads only, with its verdict), the report card rendered through the catalogs and the pending strip; the download menu with "With changes", "Clean" and "With changes (internal)"; the outline for keyboard selection.
- [`artifact-list.tsx`](../../../surfsense_local/frontend/src/features/studio/artifact-list.tsx): a row opens when `head_number` is set; a failed refine shows its reason on the open row.
- [`registry.tsx`](../../../surfsense_local/frontend/src/features/studio/viewers/registry.tsx): flashcards and quiz keyed `${id}:${head_number}`; viewers get `version` and an optional `onSelection`.
- [`html-viewer.tsx`](../../../surfsense_local/frontend/src/features/studio/viewers/html-viewer.tsx) and `streamdown-config.ts`: no scripts, no remote images, as above (M0).
- [`docx-viewer.tsx`](../../../surfsense_local/frontend/src/features/studio/viewers/docx-viewer.tsx): change rendering for revised copies; the font mapping; a text-quote selection from `window.getSelection()` with 32 characters of context. `xlsx-viewer.tsx` gains range selection and highlights; `pptx-viewer.tsx` slide selection and badges.
- The source-preview panel ([`file-viewers`](../../../surfsense_local/frontend/src/features/file-viewers/registry.tsx)) stays read-only and gains "Make a revised copy" for a supported original.

## Options considered and rejected

| Option | Why not |
|---|---|
| History in `artifact_metadata` plus `history/g<N>/` | Not constrained or queryable, mixed with progress state; ADR 0003 rejected JSON discriminators for this. |
| Every edit as a new artifact | Clutters the list, indexes every draft, loses "current". Kept only for what leaves the app: revised copies, and Save as copy later. |
| Writing edits into the user's file with a backup | Breaks "nothing edits the user's files"; Cowork corrupted OneDrive files this way ([#62140](https://github.com/anthropics/claude-code/issues/62140)); a linked file may be a cloud placeholder. |
| opencode snapshots as the version store | Need git and are off; miss files that bash and engines write (I2, E6). |
| Reusing `generation` as the head | It is bumped before a run and tests assert that; changing its meaning in place hides the change. |
| Backfilling `generation - 1` as the last success | A failed artifact can be regenerated, so `generation - 1` may itself have failed, and a cancel after persist leaves bytes the rows do not describe. Evidence, not arithmetic. |
| Failing pending jobs in the migration | Pending jobs survive in the Huey file and the existing worker deliberately runs them; failing them strands a queued job and hides a good output. |
| Keeping `studio_job(artifact_id)` and loading "the version in flight" | After a failure the version is no longer in flight, so Huey's retry would find nothing or run the user's next version twice. |
| Engine runs on the Studio queue | A worker thread cannot be stopped, and an edit would wait behind four Studio jobs sharing one model slot (02). |
| Chunking and embedding in the engines worker | Loads a second copy of the encoder into a fourth sidecar on a 16 GB laptop; the Studio worker already holds one. |
| "With changes" including internal comments by default | One click sends the user's internal notes to the counterparty; accept-all does not remove comments. |
| Rebuilding `artifacts`, or CHECKs on `kind`, `origin` and `queue` | `artifacts`' `DROP TABLE` would cascade into `artifact_files`; once `artifact_files` references `artifact_versions`, the same holds for it. |
| Workspace-wide dedup by SHA-256 | No index finds a twin across artifacts, and the saving is unmeasured; within one artifact covers restore and accept-all. |
| Passing the previous version into `render()` | Breaks the arity test and mixes two jobs; `revise_router` keeps both simple. |
| Letting the model classify a chat message as an edit | A 4B model is not reliable at routing (E4) and a wrong guess changes a deliverable; two buttons cost less. |
| Auto-applying edits to revised copies, or a model-chosen `tracked` flag | Customer files need pending and applied apart (E6); tracked changes are Word's own review model; a flag the model sets is a flag it can get wrong. |
| A `checkout_artifact` tool and a `publish_output` tool | Checkout put customer-derived binaries where bash and scripts could change them untracked; publish took a model-supplied path. The sweep plus id-taking engine tools cover both. |
| An Outputs group and an "include outputs" scope flag | Stream 01 already makes an artifact a source by filing it, and two mechanisms would disagree about what `all` means. |
| Docling on the ingest queue for output bodies | Right by [ADR 0008](../../adr/0008-two-job-queues.md)'s split, but splits one version across two workers; light extractors are enough for search. Revisit if bodies prove poor. |
| A per-turn manifest of `outputs/` | Misses aborted turns; comparing with stored heads does not. |
| HTML scripts allowed for builder pages only | The builder's template holds no script, so one rule for every HTML artifact is simpler and safe. |

## Phases

| Phase | Milestone | Scope | Depends on | Size |
|---|---|---|---|---|
| **0. HTML and markdown hardening** | M0 | `html-viewer.tsx`'s empty sandbox and injected CSP; `allowedImagePrefixes: []` in `streamdown-config.ts`; the two Vitest tests | nothing | S |
| **1. Versions** | M3 | Revision `0024` with `queue`, `approved_at` and `approved_by`, the evidence backfill and its tests; models; `start_version`, its `queue` rule and dispatch; `studio_job(artifact_id, version_id)`; `version_job` and `index_version` at a raised priority; `begin_version`, `finish_version`, `fail_interrupted_versions`, `sweep_orphan_folders`; `store_version_files` with per-artifact hard links; `commit_version` with the title rule and the existence check; the four running-state readers; delete guards; `apply_report.py`; regenerate with a prompt and a re-resolved scope; restore; fixed media retention; versioned routes and caching; progress on `head_number`; switcher, invalidation, rows that open past a failed version; the offline failure. | nothing; M0's snapshot runs before its revision | L: a backfill over users' only database plus the job state machine and panel. |
| **2. Specs and Refine** | M3 | `Built.spec`; `revise_router` and `revise(*models, …)` for summary, mind map, flashcards, quiz, html, image, infographic; schemas for the JSON formats that lack one; tier prompts; the window check; `compare`; the spec report; Refine box; chat Edit without a scope, card and `as_history`. Offered where `edit_rungs[format]` includes rung 1, "Not measured" on unmeasured models. | 1; until 05 P4a lands in M4, the offer uses 05's unmeasured default as a fixed rule (rung 1 on summary, mind map, flashcards, quiz and html, labelled "Not measured"), and from M4 it reads `capability_of(session).edit_rungs` | M–L: one function per format, plus up to five schemas if 05 §7 has not written them. |
| **3. Agent bridge** | M5 | `create_artifact` id; `revise_artifact` with local deferral; `output_files` confinement; the two-step sweep with caps; `accepted_text`; `agent` versions on `version_job`; `attach_steps`; frames; prompt line. | 1; 01 phase 3a's per-thread folders and thread-scoped tool URL; 02's tool list; a model with `agent` in its engines to be useful | M: small tools, one sweep, many touched tests. |
| **4. Revised copies and tracked changes** | M6 | `start_revised_copy` through `resolve_original`, `copy_original` and `start_workflow`; docx edits on `engine_job` and their hand-over to `index_version`; the `external` and `clean` files and the three downloads; localized download names; `revisions` and `decide`; the change-rendering fixture check; the revision list; the font mapping; review and its self-attested record; Export with the linked-root guard; then xlsx cells and pptx slides as engines land. | 1; 02 phases 0, 1 and 1b (the licence-clean docx engine, the engines queue, `start_workflow`, `docx.external`); 01 phase 3a's `copy_original` | L: engine integration, review UI, fixture work. |
| **5. Selection edits** | M9 | Resolvers for text quotes, cell ranges, slides and items; server-built ops; selection UIs; the keyboard path. | 2 for spec-backed; 4 for docx; stream 02's xlsx engine (its phase 5a) and pptx engine; 05's `selection_content` rows | M: one resolver and one selection UI per kind. |
| **6. Artifacts as sources** | M3 | Self-exclusion through 01's resolver; `inputs.sources[].version`; the newer-source hint. | 1; 01's scope resolver and filing (its phases 0 and 5) | S. |
| **7. Keeping and forking** | M10 | Pin and configurable retention; Save as copy (`artifacts.derived_from_version`, kind `copy`); `markdown` and `csv` viewers with `allowedImagePrefixes: []`; PDF export through `export_job` with Office support; a filter on head title and body in Studio's list; cross-artifact dedup if measured disk use asks for it. | 1; 04's RT3b for PDF | M. |

Phases 2, 3 and 6 can run in parallel after 1. Phase 3 ships in M5 with 06's Answer / Work on files switch, and M5 turns the agent on in installers only once it has shipped, so files the agent writes are never invisible to the user. Phase 4 carries the B2B value; it waits on 02's clean-room engine work in M1 and ships with `docx.external` in M6.

## Tests

Changed:

- `tests/integration/artifacts/test_constraints.py::test_an_artifact_holds_one_file_per_role` becomes `test_a_version_holds_one_file_per_role`: two versions may each hold a `primary`, a second in one version is an `IntegrityError`.
- `tests/integration/artifacts/test_routes.py::test_a_failed_artifact_can_be_regenerated` (lines 575–579 fail only the document) also fails the v1 version row, keeps `generation == 2`, adds a null head and one pending v2, and expects the queue to hold `(artifact_id, v2_id)`.
- `tests/integration/worker/test_studio.py::test_persist_stores_a_primary_blob` expects `v1/` and a `version_id`. The four exec tests are untouched by this stream; they change when stream 02 replaces `exec()`.
- `tests/unit/artifacts/test_quiz_progress.py::test_a_stale_generation_is_treated_as_an_empty_run` and `test_flashcard_progress.py::test_a_stale_generation_is_treated_as_an_empty_deck` scope by head.
- `tests/integration/agent/test_tool_endpoint.py::test_it_offers_its_tools_with_flat_schemas`: its assertion `assert list(listed) == ["search_sources", "create_artifact"]` expects stream 02's order with `revise_artifact` after `edit_document`; the flat-schema checks cover it; the prompt test names it and the prompt stays under 4,000 characters.
- `local_image_demand` and `llm/router.py` tests read versions.
- Frontend: `artifact-list.test.tsx` keeps "disables opening a failed artifact" for a failed v1 and adds "opens the head while a refine has failed"; `artifact-panel.test.tsx` covers the switcher, a stale `409` and invalidation; `use-studio.test.ts` adds version toasts and polling while `pending_version` is set.
- Unchanged by design: `test_studio_job_router.py`'s equality and arity tests, `test_a_document_carries_at_most_one_artifact`, both delete tests for an idle artifact.

New:

- **Migration:** metadata comparison after `0024`, raw-SQL key included; the backfill run twice inserts nothing the second time; one case per table row above, including a never-succeeded regenerate (failed v1, failed v2: no head), ready then failed then failed (legacy head, number 2, generation 1's body), a cancel after persist (hash mismatch: failed, no head), a failure after the `rmtree` (missing file: no head), and a pending regenerate with evidence (legacy head plus pending version).
- **Queue across the upgrade:** an artifact queued with `studio_job(artifact_id)` before the upgrade runs to ready afterwards.
- **Retry:** fail once, start a new version, run the retry: it does not run the new version and the new version runs once.
- **Queue rule:** a `review` and an `edit` with a complete plan get `engines`; a selection edit, chat Edit and a workflow get `studio`; a mismatched `queue` argument raises.
- **Index hand-over:** an engine edit's chunks are written by the Studio worker; importing `modules.engine_runs.tasks` does not import `worker.ingestion.indexing`; a handed-over version survives a Studio worker restart as `pending` and runs to ready; `index_version` runs ahead of a queued generation.
- **Head:** a failed refine leaves head, document status, body and chunks unchanged; a cancel that wins the race moves nothing; rename then refine keeps the rename; a refine whose remote model is unreachable fails with that reason and moves nothing.
- **Running state:** an image refine in flight makes `local_image_demand` return `IMAGE_GEN`; a local model delete is refused while a refine runs; `notify_artifact_updates` sends the version's status.
- **Delete:** delete during a pending refine cancels it; delete during a processing refine answers `409`; a worker that commits after a delete leaves no `artifacts/<id>/` folder; the start sweep removes an orphan folder and leaves an in-flight one.
- `409` for a stale base and for a version in flight; restore makes a version with the same checksum, hard-linked where possible; podcast retention keeps head and two others; a purged version refuses restore; only the head's chunks exist after three versions.
- **Revised copy:** the original's bytes and modification time are unchanged after v1 and v2; `base_sha256` equals `content_hash`; an online-only original is a `409` before any version exists; every change in v1 and v2 is a tracked revision by the workspace's author, and the engine is never called with `allow_untracked_accept`.
- **Downloads:** a revised copy with an internal comment downloads without it by default; "With changes (internal)" keeps it; `clean` holds no internal comment; a suffix passed by the client names the file, and none falls back to English; a title `CON` downloads as `_CON …`.
- **Review:** approve records the typed name and the time; the next version starts unreviewed; with `write_properties` the download carries `docProps/custom.xml` and the stored file's checksum is unchanged.
- **Report:** an agent edit with one failed op saves nothing and fails the version with the report; a workflow run with `partial=True` is ready with the failed op's code; zero applied fails; output equal to input fails; a model reply claiming success never sets a status; an op's `code` renders through the catalog in a non-English locale, and an unknown code shows `message`.
- **Sweep:** new, changed and unchanged files; `_work/`, `~$` and invalid OOXML ignored; the confinement cases above; the 51st file is reported, not published; a file changed between scan and copy fails its version; an aborted turn's file swept next turn; two threads with the same file name make two artifacts; a derived artifact is never versioned by the sweep.
- **Viewers:** an HTML artifact's script does not run and its remote image is not fetched; a Vitest DOM test renders a fixture's insertions, deletions and comment with change rendering on.
- **Accessibility:** the report card, the revision side list and the version switcher pass an axe check in their Vitest tests (an axe package is a new dev dependency; `package.json` has none today); a selection edit can be made from the outline with the keyboard alone.
- **Chat:** the turn after an Edit carries the card's line in history.
- **Sources:** an artifact grounds a Studio job; an artifact is excluded from its own refine.
- **Export:** a destination inside a linked root is refused.

## What this changes in existing ADRs and proposals

- **[ADR 0003](../../adr/0003-artifacts-as-documents.md), In the desktop app:** artifacts hold append-only versions; only the head is indexed, and its stale-generation window shrinks to zero because the head moves in the re-indexing transaction; one blob per role per version. "Generation source files are transient … not persisted artifact files" changes: the `spec` and `plan` roles persist a version's structure and its engine operations. `created_by_tool_call_id` and `updated_by_tool_call_id` are superseded by the version's `step_ref` and stay unwritten. Fix the stale line that the documents route leaves `artifacts/<id>/` on disk (`documents/router.py::delete_document` removes it). Obligation 2 stands.
- **ADR 0040, shared with 02,** "Edits run shipped engines on model-written plans, make append-only versions, and never write the user's file", recording decisions 2, 3, 4, 5, 11, 12 and 13, which bind every future entry point, plugins included. The number is the README's.
- **[ADR 0010](../../adr/0010-studio-builders-not-sandboxes.md), Where the code stands:** spec-level edits keep the builder rule; file edits run shipped engines on model-written plans, which ADR 0040 records. [ADR 0028](../../adr/0028-model-written-code-runs-with-approval.md) is unchanged by this stream: no edit runs model-written code.
- **[ADR 0008](../../adr/0008-two-job-queues.md):** the engines queue never embeds; it hands finished runs to the Studio queue for indexing.
- **[Export bundle contract](../../contracts/03-export-bundle.md):** the workspace bundle carries artifact versions, as under Export.
- **[Agent README](../agent/README.md):** drop "Editing sources or artifacts, undo, git history" from Out of scope; "nothing edits the user's files" becomes a tested rule. **[`02-tools.md`](../agent/02-tools.md):** `create_artifact` returns id and version; `revise_artifact` joins 02's engine tools.
- **[studio](../../architecture/studio.md), [data model](../../architecture/data-model.md), [agent](../../architecture/agent.md):** rewrite Regenerate, routes, viewers, tables and the `artifacts/<id>/` layout at phase 1; agent Known gaps lose "outputs do not become artifacts" and "no thread or step" at phase 3.
- **[Plugins protocol](../plugins/01-protocol.md):** it notes that the only artifact route generates from documents. The version routes here are what a later `artifact` domain would wrap.
- **Asks of [02](02-skills-and-engines.md):** `engine_job` ends a successful run by handing the version to `index_version` (files, report, plan, changes and views recorded; `queue` set to `studio`; status back to `pending`) instead of calling `commit_version`, so `queue` is set at creation and changed only by that hand-over; ops stay in the `plan` role; `EngineResult.checks` carries pass or fail per check id; reports carry `{code, values}` per operation and per `must_tell_user` line; `docx.external` and accept-all write the `external` and `clean` files in the job that makes the version; `revise_artifact` sits after `edit_document` in `TOOL_ORDER`, which has no `publish_output` or `checkout_artifact`; the provenance bullet points to `attach_steps`.
- **Asks of [01](01-sources-and-folders.md):** `output_path` is relative to the thread's `outputs/` and unique on `(chat_thread_id, output_path)`; thread delete nulls `output_path` on the thread's artifacts; folder delete goes through `versions.guard_delete`.
- **Asks of [04](04-runtime-and-packs.md):** the engines sidecar loads no embedding encoder, since chunks and vectors are computed in the Studio worker; the font mapping in `docx-viewer.tsx` is taken here, using RT2's WOFF2 files; phase 7's PDF export is a fourth caller of `convert()`, in an export job outside `transact()`; the interface says "Office support".

## Open questions

1. **Comparing two arbitrary docx versions** needs a compare engine: the skills project's `compare` after the clean-room rewrite (stream 02), Python-Redlines (MIT, .NET binaries in the wheel, size unmeasured against the installer budget, stream 04), or text diff only?
2. **Is docx-preview 0.4.0's experimental change rendering faithful** on engine output, including moves, formatting changes and comments in footnotes? Phase 4's fixture check decides.
3. **Does docx-preview fetch externally linked images** (`r:link`, `TargetMode="External"`) in an agent-written or customer docx? If it does, the DOCX viewer needs the same no-remote-load rule as HTML, most simply a renderer-wide CSP, which would also cover pptx and xlsx previews.
4. **Rejecting one xlsx or pptx change.** Neither format has usable native tracked changes. Is "restore these cells or this slide from the base" as a new version the right reject, or only whole-version restore?
5. **Retention numbers** for media. The README's disk-usage view counts versions; does phase 7 also need a per-artifact line?
6. **Can opencode pass a call id to MCP tools** (1.18.34 or 2.x), so `step_ref` is exact for tool-made versions instead of matched after the turn?
7. **Upgrade cost:** how long does the evidence backfill take on a library with thousands of artifacts and large podcasts? Measure on a fixture before release; if it is long, hash only rows whose size differs and trust size plus modification time for the rest.
