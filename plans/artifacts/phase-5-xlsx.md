# Phase 5 — XLSX Artifact Pipeline

**Status:** Complete (2026-08-16).
**Parent spec:** [`artifacts-overhaul.md`](./artifacts-overhaul.md).
**Depends on:** phase 3 verification service and phase 4 shared OOXML guard.

## 1. Shipped scope

Phase 5 added spreadsheet generation, structural verification, persistence, and an authenticated read-only grid without changing the artifact schema or API.

- The sandbox ships an XLSX skill backed by preinstalled XlsxWriter.
- `.xlsx` has a structural `FormatAdapter` with the canonical spreadsheet MIME.
- Verification is programmatic: no conversion, rasterization, vision review, or preview file.
- Binary persistence uses the existing primary artifact role.
- The artifact panel lazy-loads a native spreadsheet viewer for XLSX manifests.

Generic unknown formats, public artifact viewing, and cross-format hardening are phase 8. Legacy report and Typst removal is documented separately in phase 7.

## 2. Persistence

An XLSX artifact is one `Document(document_type=ARTIFACT)` plus one `Artifact(format="xlsx")`. Its files are:

- a primary `.xlsx` file;
- no preview.

The document owns searchable Markdown under `/documents/` and follows ordinary chunking, indexing, search, move, rename, and deletion behavior. Artifact revisions restore the current workbook plus Markdown context and save with `artifact_id + expected_generation`.

XLSX required no migration, document subtype, chunk table, search branch, or format-specific artifact route.

## 3. Verification

The XLSX adapter reuses the shared OOXML trust boundary and verifies:

- required workbook package parts;
- at least one worksheet and one non-empty cell;
- a cached value for every formula cell;
- no cached Excel error literal;
- a maximum of 100,000 cells.

A successful receipt records `visual="not_required"` and binds the primary hash. It has no page count, preview path, or preview hash. Verification inspects the workbook bytes but never recalculates or rewrites them.

## 4. Generation skill

The XLSX skill authors deliverable-named `.xlsx` and `.py` files with XlsxWriter. It teaches reusable formats, deliberate widths, frozen headers, multiple sheets, formulas with computed cached values, and recalculation-on-open.

The generation flow is:

1. create the workbook and complete Python source in the sandbox;
2. call `verify_artifact` on the workbook;
3. call `save_artifact` with the primary path and no preview;
4. for revisions, call `load_artifact_for_revision`, edit the restored workbook with a format-aware library, and save with the returned generation.

The Python generation source remains transient in the sandbox. The Markdown representation summarizes sheets, columns, and key figures for search and accessibility.

## 5. Native viewer

The viewer registry maps the spreadsheet MIME to a client-only `XlsxViewer`. The viewer:

- rejects oversized files before fetch and again before parse;
- parses through the isolated `parseWorkbook(bytes): WorkbookView` boundary;
- uses ExcelJS for workbook values and `ssf` for formatted numbers and dates;
- shows cached formula results;
- renders sheet tabs and a virtualized read-only grid with row and column headers;
- limits each displayed sheet to 500 rows and directs users to download the full workbook;
- degrades corrupt or unsupported workbooks to the shared unviewable state while preserving download.

Charts, pivot tables, macros, editing, and full Excel emulation are outside the XLSX viewer contract.

## 6. Verification evidence

- Unit coverage exercises clean workbooks, formula caches, missing caches, Excel errors, empty content, the cell ceiling, and receipt behavior.
- Receipt tests prove XLSX never enters conversion, rasterization, or vision.
- Integration coverage proves primary-only persistence, post-verification mutation rejection, restoration of the current primary, optimistic revision, and blob purge.
- Parser tests cover formatted values, formula results, row truncation, oversized payloads, and corrupt workbooks.

## 7. Exit criteria

1. XLSX requests route to the spreadsheet skill.
2. The generated workbook verifies without a rendered preview or visual review.
3. Save and revision use the same document-backed artifact model as PDF, DOCX, and PPTX.
4. The authenticated artifact panel renders the real workbook in a native grid and downloads the original `.xlsx`.
5. No XLSX-specific schema, persistence API, search path, or document editor path exists.
