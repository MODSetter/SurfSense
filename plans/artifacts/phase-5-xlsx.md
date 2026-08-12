# Phase 5 — XLSX Skill + Native Grid

**Status:** Planned. Persistence/API support and service-level primary+source coverage are already in place; the XLSX adapter, skill, and viewer in this phase are not.
**Parent spec:** [`artifacts-overhaul.md`](./artifacts-overhaul.md).
**Depends on:** phase 3 verification service and phase 4 shared OOXML guard.

## 1. Goal and scope

Ship spreadsheet authoring, programmatic verification, and a read-only native grid without changing the artifact schema or API.

In:

- total generic format-adapter behavior if not already complete;
- XLSX skill and structural adapter;
- programmatic receipt path with no rasterization, vision, or preview;
- `XlsxViewer`;
- public/share-token artifact manifest and file access required before phase 6 removes legacy public preview.

Out: legacy report/Typst deletion (phase 6).

## 2. Persistence contract already available

An XLSX save is:

- one `Artifact(format="xlsx")` over one artifact `Document`;
- primary `.xlsx` `ArtifactFile`;
- private source `.py` `ArtifactFile`;
- no preview;
- searchable Markdown on the document under `/documents/Artifacts/`;
- ordinary document chunking and search;
- `artifact_id + expected_generation` revisions;
- artifact manifest/download/file routes.

Existing service tests prove this shape. This phase must not add a document type, migration, chunk table, document API branch, or search side channel.

## 3. Verification adapter

`FormatAdapter` represents rendered verification as an optional policy. XLSX has no rendered policy: after structural checks, verification issues a receipt with visual review not required, no page count, and no preview hash.

The adapter reuses the shared OOXML trust boundary and checks:

- workbook and required parts exist;
- at least one sheet and non-empty cell;
- every formula cell has a cached result;
- cached results are not Excel error literals;
- total cells stay below the parser/viewer safety ceiling.

The adapter owns `.xlsx` and the canonical spreadsheet MIME.

Verification only inspects. It never recalculates or rewrites the workbook.

## 4. Skill

Author with preinstalled XlsxWriter. The skill covers formulas, number formats, header styles, widths, panes, and multiple sheets.

Every formula must include a computed cached result via XlsxWriter's value argument. The same script also sets recalculation-on-open. This keeps the primary complete for the browser grid while Excel/LibreOffice recalculates on open.

The flow is:

1. generate deliverable-named `.xlsx` and `.py`;
2. `verify_artifact(<workbook>.xlsx)`;
3. `save_artifact(path=..., source_path=..., ...)`;
4. on revision, load by `artifact_id` and save with current expected generation.

## 5. Viewer

Register the spreadsheet MIME behind a lazy-loaded `XlsxViewer`:

- fetch the primary artifact file URL from the manifest;
- reject oversize files before mounting/parsing;
- parse behind one `parseWorkbook(bytes): WorkbookView` module boundary;
- use ExcelJS for workbook/style parsing and `ssf` for formatted display values;
- render a read-only grid with sheet tabs, row/column headers, and a row cap;
- use `content-visibility: auto` for rows;
- degrade corruption, oversize, or unsupported workbook features to download.

Charts, pivot tables, editing, and full Excel emulation are out of scope. ExcelJS remains isolated so the parser can be replaced without rewriting the viewer.

## 6. Generic unknown formats

An unknown suffix resolves to a generic adapter: bounded non-empty bytes, canonical `application/octet-stream`, no rendered policy. It verifies, persists through the same document + `Artifact`/`ArtifactFile` service, and renders as a download fallback. Persistence must never enumerate XLSX or any future format.

## 7. Public artifact access

Add token-scoped manifest/file/download access constrained to artifacts produced by the shared thread. Reuse the same manifest and viewer registry rather than forking the panel. Workspace-authenticated artifact routes remain unchanged.

## 8. Checks

- Adapter fixtures for formulas/caches/errors/empty workbooks/cell ceiling/OOXML attacks.
- Programmatic receipt emits no preview and never calls renderer or vision.
- Primary+source save, source privacy, optimistic revision, and stale-generation failure.
- LibreOffice recalculation smoke check.
- Parser unit tests for values, number formats, and styles.
- Viewer smoke/Playwright coverage for formula values, style, tabs, oversize, and corrupt fallback.
- Unknown format verifies and downloads with no code path special-casing it.
- Public-token isolation across threads/workspaces.

## 9. Exit criteria

1. XLSX generates, verifies programmatically, persists primary+source, renders in the native grid, and downloads the real workbook.
2. All four launch formats operate through the same artifact model and routes.
3. Unknown binaries persist and download through the generic adapter.
4. No active routing reaches legacy report/resume tools.
5. Public shared threads can view/download their artifacts before phase 6 removes legacy public preview.
