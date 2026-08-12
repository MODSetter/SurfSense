# Phase 6 — Legacy Deliverable Demolition

**Status:** Planned.
**Parent spec:** [`artifacts-overhaul.md`](./artifacts-overhaul.md).
**Depends on:** phase 5 completion and proof that no active route invokes legacy report/resume generation.
**Goal:** Delete the legacy `Report`/Typst system. Do not migrate legacy rows into either `Artifact` or `Document`.

## 1. Ordering

Land in this order, keeping each change green:

1. Static legacy cards and release-note warning.
2. Repoint remaining library/public surfaces to dedicated artifact APIs.
3. Remove agent/frontend/backend legacy code, including clone-time report handling.
4. Drop legacy data/model and dependencies.

Shared-thread cloning is the last live `Report` writer: historical `generate_report` parts currently cause clone-time report inserts. Remove that behavior before dropping the table.

## 2. Legacy behavior

Old `generate_report`/`generate_resume` parts render a static card:

> Generated with the previous artifact system — no longer available. Ask me to regenerate it.

The card performs no fetch and opens no panel. Release notes warn users to export old deliverables before upgrading.

There is no backfill, `migrated_from_report_id`, lazy conversion, Typst compile, or mapping to the dedicated artifact schema.

## 3. Demolition inventory

### Agent layer

- Delete `generate_report` and `generate_resume` implementations, registrations, catalogs, prune names, and streaming handlers.
- Delete the legacy report-writing skill and resume-specific tests.
- Keep `save_artifact`, `verify_artifact`, and `load_artifact_source` as the format-oriented system.

### Frontend

- Delete the report panel/atom, version switcher, reports API/types, legacy artifact kinds, and Typst export special cases.
- Route current artifact cards, panel, library, downloads, and caches exclusively by `artifact_id` through dedicated artifact APIs.
- Keep static legacy-part matching only for old messages.
- Retire document-mode editing as defined by the product plan; memory/team-memory Plate remains.

### Backend

- Delete report routes and Typst public preview.
- Delete report snapshot/clone readers, lookup maps, ID rewrites, and clone-time `Report` inserts.
- Replace remaining Typst PDF export for ordinary documents with the selected non-Typst path.
- Delete report schemas/templates/helpers.

### Data and dependencies

- Drop `reports` and remove `Report` only after all writers/readers are gone.
- Remove Typst/rendercv assumptions.
- Keep `pypdf`, LibreOffice, and Poppler because artifact verification uses them.
- Leave document version/revision tables to the git-native KB cut; they are unrelated to dedicated artifacts.

## 4. Dedicated artifact boundary during demolition

The artifacts library lists `GET /workspaces/{workspace_id}/artifacts`. It does not query documents or infer generation from document metadata/file kinds.

Phase 6 must not:

- convert legacy reports to `Artifact`;
- reintroduce document-backed artifacts;
- add document artifact routes;
- collapse artifact and document search tables;
- change `/artifacts/**` projection;
- alter optimistic `artifact_id + expected_generation` revisions.

## 5. Checks

- After each PR, run the full relevant suite.
- Legacy names remain only in specs, changelog/release notes, and the static old-message matcher.
- Shared-thread cloning with old report parts writes no `Report`.
- After the drop, no runtime `Report`, Typst, report API, or old tool references remain.
- Old threads render the static card without network access.
- Artifacts library and panel use only dedicated artifact list/manifest/download routes.
- Phase 1–5 artifact exit criteria remain green.

## 6. Exit criteria

1. `reports` is dropped with no migration.
2. Old tool parts render static unavailable cards.
3. Dedicated artifacts remain `Artifact`/`ArtifactFile`/`ArtifactChunk`.
4. No current UI or backend artifact path uses document identity or routes.
5. Typst and obsolete report/resume generation are absent from runtime dependencies and code.
