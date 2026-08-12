# Phase 3 — Verification Service + DOCX

**Status:** Complete (2026-08-12).
**Parent spec:** [`artifacts-overhaul.md`](./artifacts-overhaul.md).
**Depends on:** phase 2 sandbox and PDF path.

## 1. Shipped scope

- Backend-owned `verify_artifact` orchestration and progress events.
- Structural format adapters, isolated conversion/rasterization, contextual vision review, and signed receipts.
- PDF migrated from model-sequenced scripts to the service.
- DOCX skill and OOXML structural adapter.
- DOCX canonical MIME and PDF rendered policy.
- Primary + preview + source artifact-file shape.
- `PdfPreviewViewer` with missing-preview fallback.

## 2. Verification architecture

The service performs, in order:

1. Read and structurally inspect the primary bytes.
2. Snapshot those bytes in a fresh build directory.
3. Convert rendered formats with an isolated LibreOffice profile and verify output existence.
4. Enforce page ceilings, rasterize, and load rendered evidence into backend memory.
5. Review every page in contextual windows and separate blocking defects from warnings.
6. Issue an HMAC-signed receipt bound to workspace, sandbox, adapter, primary hash, optional preview hash, verdict/reason, and expiry.

`save_artifact` verifies that receipt and hashes the exact primary/preview bytes being persisted. It stores verification metadata on `Artifact.metadata`. No document metadata is involved.

The service emits progress for checking, converting, rendering, and reviewing. A blocking result creates no receipt. A visual model unavailable/quota-exhausted result may issue an explicit “could not verify” receipt if no known defect exists.

## 3. DOCX

The DOCX adapter uses the shared OOXML trust boundary: duplicate/encrypted parts, entry counts, compressed/uncompressed limits, and required parts are validated before XML is trusted. DOCX-specific checks cover invalid table widths/shading, literal bullets, missing grids, and TOC/outline inconsistencies.

The skill authors with the preinstalled Node `docx` package, uses a deliverable-derived filename, generates the whole reflowing document, then calls the generic verify/save tools. It does not implement conversion, rasterization, receipts, or source loading.

The adapter owns the canonical WordprocessingML MIME. The saved artifact has:

- primary `.docx`;
- receipt-bound preview `.pdf`;
- private generation source.

The manifest omits source. The viewer renders preview and the stable download serves current primary.

## 4. Dedicated persistence assumptions

- All rows are `Artifact`/`ArtifactFile`; DOCX never creates a `Document`.
- Revision starts with `load_artifact_source(artifact_id)` and saves with `artifact_id + expected_generation`.
- Retitle leaves `/artifacts/<authored path>.md` unchanged.
- Git-backed search content converges into `ArtifactChunk`; non-git content indexes directly.
- Deletion captures and purges all artifact blob roles through artifact storage.
- Search citations use `ARTIFACT_CHUNK`.

## 5. Checks

- Pure adapter fixtures for valid and malformed OOXML.
- Receipt round-trip, tampering, expiry, audience, and hash mismatch tests.
- Mocked-sandbox DOCX save with primary/preview/source, source omitted from result/manifest, and stale receipt refusal.
- Later-turn optimistic revision keeps the same artifact ID, increments generation, and uses stored source.
- Live OpenSandbox conversion/rasterization and canonical MIME check.
- Delete removes all reachable primary/preview/source blobs.

## 6. Exit criteria

1. PDF and DOCX verify through one backend service with no skill scripts.
2. DOCX renders through its PDF preview and downloads the real DOCX.
3. Source remains private but loadable by the revision tool.
4. Failed/stale revisions preserve the previous generation.
5. Phase 4 can add PPTX as an adapter, skill, registry entry, and tests without changing persistence or API contracts.
