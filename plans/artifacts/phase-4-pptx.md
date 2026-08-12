# Phase 4 — PPTX + Format-General Rendered Verification

**Status:** Complete (2026-08-12).
**Parent spec:** [`artifacts-overhaul.md`](./artifacts-overhaul.md).
**Depends on:** phase 3 verification service and preview viewer.

## 1. Shipped scope

- Adapter-owned rendered policy: minimum rendered text, exact page-count expectation, and review kind.
- Shared OOXML parser trust boundary.
- PPTX structural adapter, canonical MIME, and slide-aware rendered verification.
- PPTX skill using preinstalled `python-pptx`.
- PPTX MIME mapped to the existing `PdfPreviewViewer`.

No schema, persistence path, receipt shape, API route, or viewer component was added for PPTX.

## 2. Verification

PPTX structural checks validate package parts, slide order/count, relationships, hidden slides, drawable shapes, canvas geometry, crop bounds, and embedded media references. Rendered verification:

- treats slides as independent visual units;
- permits low-text/chart-only slides;
- requires converted PDF page count to equal source slide count;
- checks the ceiling before expensive conversion where source count is known;
- still reviews the complete deck once.

The adapter owns the presentation MIME and PDF rendered policy. The generic receipt gate binds primary and preview hashes exactly as for DOCX.

## 3. Dedicated artifact flow

PPTX persists as one `Artifact` with primary, preview, and private source `ArtifactFile` rows. Its searchable representation uses `/artifacts/**` and `ArtifactChunk`; it never enters document persistence.

Create returns `artifact_id` and generation. Revision loads source by artifact ID and requires the expected generation. The manifest and immutable file URLs are artifact routes. Search results are source-qualified artifacts and citations are `ARTIFACT_CHUNK`.

## 4. Rendering

The panel downloads the real `.pptx` and displays the receipt-bound PDF preview. Missing preview degrades to the shared unviewable/download state.

PPTX generation is independent of the video-media pipeline; no PPTX exporter remains in media code.

## 5. Checks

- Adapter fixtures for package/count/relationship/hidden-slide/geometry/crop defects.
- Service checks for pre-conversion ceiling and dropped converted pages.
- Slide/document review framing under one verdict contract.
- Dedicated artifact create, stale-receipt refusal, private source, optimistic revision, stable path, and blob purge.
- Live OpenSandbox generation, LibreOffice conversion, Poppler rasterization, receipt, and canonical MIME.

## 6. Exit criteria

1. PPTX generates, verifies, persists, previews, and downloads as the real deck.
2. Conversion dropping a slide cannot receive a receipt.
3. Slide-deck requests route to the PPTX skill.
4. No document model, document route, or media exporter participates.
5. Phase 5 needs no persistence/API migration to add XLSX.
