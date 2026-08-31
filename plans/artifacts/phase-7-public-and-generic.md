# Phase 7 — Public, Generic, and Hardened Artifacts

**Status:** Planned.
**Parent spec:** [`artifacts-overhaul.md`](./artifacts-overhaul.md).
**Depends on:** phase 5 XLSX pipeline and phase 6 legacy demolition.

## 1. Goal

Complete the format-independent artifact contract by making artifacts available in public chat snapshots, accepting safe download-only formats through a generic adapter, and closing the remaining XLSX quality gaps.

Phase 7 extends the existing artifact service and viewer registry. It does not introduce another persistence model, public artifact copy, panel, export system, or format-specific API.

## 2. Scope

In:

- a generic adapter for unknown binary formats;
- share-token-scoped artifact manifests, primary/preview content, and downloads;
- reuse of the artifact panel and viewer registry in public chats;
- XLSX parser and viewer fidelity for common cell styles;
- adversarial OOXML, stale-generation, LibreOffice, and browser coverage;
- documentation and regression guards for the completed contract.

Out:

- persistence or public access for transient generation source files;
- public artifact editing or revision;
- retained historical artifact generations;
- replacement of existing public image, podcast, or video-presentation delivery;
- spreadsheet editing, charts, pivot tables, macros, or full Excel emulation;
- restoration of legacy reports, resumes, Typst, or document export routes.

## 3. Generic format adapter

Unknown file suffixes resolve to one generic adapter instead of failing format lookup. The adapter:

- accepts bounded, non-empty bytes;
- uses `application/octet-stream`;
- has no rendered-verification policy;
- issues a programmatic receipt bound to the primary hash;
- produces no preview;
- persists through the existing artifact service;
- renders through the shared download-only fallback.

Unknown content is always served as an attachment. The backend must not infer an inline-safe MIME from untrusted bytes or add suffix checks to persistence. Existing size limits remain the trust boundary; the generic adapter does not introduce a second limit.

Generation-source handling is unchanged: source files remain transient sandbox inputs and are not persisted as artifact roles.

## 4. Public artifact contract

### 4.1 Authorization

A public share token grants access only when:

1. the token resolves to a public chat snapshot;
2. the requested artifact ID is in that snapshot's artifact allowlist;
3. the artifact belongs to the snapshot's workspace and originating thread.

Every public manifest, file, and download route applies the same authorization helper. Invalid tokens, cross-thread IDs, cross-workspace IDs, file IDs outside the artifact's visible primary/preview roles, and deleted artifacts return `404` without disclosing which check failed.

Chat messages remain immutable snapshot data. Artifact IDs are live references to the artifact's current generation; phase 7 does not retain or expose historical artifact generations.

### 4.2 Routes

Add token-scoped equivalents of the authenticated read surface:

- `GET /public/{share_token}/artifacts/{artifact_id}/manifest`
- `GET /public/{share_token}/artifacts/{artifact_id}/download`
- `GET /public/{share_token}/artifacts/{artifact_id}/files/{file_id}/content`

The public manifest uses the same artifact metadata and file-role shape as the authenticated manifest, but emits public URLs. It includes only `primary` and `preview` files; generation sources are not persisted.

Download returns the real primary artifact with a safe filename and `Content-Disposition: attachment`. A Markdown-only artifact downloads the document's Markdown snapshot through the same route. File content supports only receipt-bound primary and preview files.

The existing `/public/{share_token}/artifacts/{artifact_id}/content` media route remains a compatibility endpoint for current public image/tool cards. It must delegate authorization and primary-file lookup to the same helper instead of becoming a second access policy. Existing podcast and video-presentation routes remain unchanged.

Public routes require no session cookie and must not redirect to authentication. Cache headers must not make one token's private response reusable for another token.

## 5. Public viewer integration

Public tool cards resolve artifact manifests with the share token and open the existing artifact panel. `ArtifactViewerContent` and the viewer registry remain the single rendering path for authenticated and public artifacts.

- PDF uses the PDF viewer.
- DOCX and PPTX use their receipt-bound PDF preview.
- XLSX uses the native grid.
- Markdown uses the Markdown viewer.
- Unknown formats use the download fallback.

The panel's download action uses the manifest-provided public download URL. Authentication state must not be consulted when a share token is present. Loading, missing, corrupt, oversized, and unviewable states reuse the existing artifact UI.

## 6. XLSX hardening

Extend the parser/view model only for common, bounded presentation details:

- font weight and color;
- fill color;
- borders;
- horizontal alignment;
- number and date display formats already represented by `ssf`.

The grid remains virtualized through `react-data-grid`; a second `content-visibility` mechanism is unnecessary. Unsupported style features degrade to plain cells and never block workbook values or download.

Harden OOXML verification fixtures for:

- path traversal and backslash-normalized traversal;
- external relationships;
- oversized or excessive ZIP members;
- excessive compression ratios;
- missing workbook, worksheet, relationship, and content-type parts;
- malformed XML and invalid worksheet targets.

Add a live LibreOffice smoke check that opens/recalculates a generated workbook and confirms the workbook remains valid. Keep this environment-dependent check separate from deterministic unit tests.

## 7. Required checks

### 7.1 Generic formats

- unknown suffix verifies with `application/octet-stream`;
- empty and oversized payloads fail before persistence;
- receipt binds the primary hash and contains no rendered fields;
- manifest falls back to download-only viewing;
- authenticated and public downloads force attachment disposition.

### 7.2 Public access

- valid token can read only allowlisted artifact manifests and files;
- another thread, workspace, token, or artifact ID receives `404`;
- file IDs outside the artifact's visible primary/preview files are never listed and always receive `404`;
- Markdown-only and binary primary downloads return correct bytes and filenames;
- deleted artifacts and stale file IDs fail closed;
- public DOCX/PPTX preview and XLSX primary routes use the shared viewer registry.

### 7.3 XLSX

- adversarial OOXML fixtures cover every shared package guard;
- stale-generation revision fails without changing files or generation;
- parser tests cover formulas, dates, number formats, common styles, sheet tabs, row caps, corrupt bytes, and size rejection;
- Playwright covers sheet switching, cached formula values, styled cells, truncation messaging, download, and corrupt fallback;
- one sandbox-to-save integration generates a real XlsxWriter workbook, verifies it, persists it, and loads it in the viewer;
- the LibreOffice smoke check validates recalculation compatibility where the binary is available.

## 8. Delivery order

1. Add the generic adapter and focused verification tests.
2. Centralize public artifact authorization and add token-scoped routes.
3. Connect public tool cards and the existing panel to public manifest URLs.
4. Add XLSX OOXML, parser, style, browser, and LibreOffice coverage.
5. Run cross-format regression checks and update artifact documentation.

Each step leaves one format-neutral path. If public integration or XLSX hardening requires a format-specific persistence branch, stop and repair the shared boundary instead.

## 9. Exit criteria

1. Any bounded, non-empty unknown binary can verify, persist, and download safely without a format-specific code change.
2. A public chat can view and download every allowlisted artifact format through token-scoped URLs.
3. Public access cannot reveal files outside the visible primary/preview roles or artifacts outside the shared thread and workspace.
4. Authenticated and public surfaces use the same manifest model, panel, and viewer registry.
5. XLSX verification rejects hostile OOXML packages and the viewer preserves common formatting while remaining bounded.
6. Real XlsxWriter output passes verification, persistence, LibreOffice smoke, and browser viewing.
7. PDF, DOCX, PPTX, XLSX, Markdown, and unknown-format regressions remain green after the public path is enabled.
