# Phase 4 — `pptx` and format-general rendered verification

**Status:** Complete (2026-08-12). Unit, database-backed integration, and live
OpenSandbox checks pass for PPTX generation, LibreOffice conversion,
rasterization, signed receipts, and canonical MIME persistence.
**Parent spec:** [`artifacts-overhaul.md`](./artifacts-overhaul.md) (§6.3
verification, §7.1 skills, §8 rendering).
**Depends on:** phase 3 complete.
**Ships to users:** "make me a slide deck" produces a real `.pptx` with an
inline PDF preview; video presentations remain a separate explicit request.

---

## 1. Scope and measured corrections

Phase 3's primary/preview/source persistence, receipt gate, renderer, and
`PdfPreviewViewer` were reusable. Its rendered verification was not fully
format-general:

1. Converted files always used PDF's 20-character near-blank rule, which rejects
   valid title-divider and chart-only slides.
2. Vision was told every artifact was a flowing document, where content
   continuing across a boundary is normal. Slides are independent.
3. The service did not compare a format's known source count with the converted
   PDF count, so a converter could omit a slide without detection.
4. The sandbox Dockerfile copied skills by name, so a new repo skill would not
   replace a same-named base-image skill.

This phase fixes those boundaries once, then adds PPTX. It does not add a new
viewer, persistence path, receipt shape, database schema, or dependency.

---

## 2. Format-general verification work

### 2.1 Adapter-owned rendered policy

`FormatAdapter` owns:

- `rendered_min_chars` — 20 for prose, 0 for visual slides.
- `expects_exact_page_count` — PPTX compares its structural slide count with
  the converted PDF's page count.
- `review_kind` — `document` or `slides`, selecting framing while one shared
  severity and JSON contract remains in `vision.py`.

When structural markup supplies a count, the service checks the ceiling before
conversion. Formats such as DOCX that only gain a count after pagination retain
the post-conversion check.

### 2.2 Shared OOXML trust boundary

`formats/ooxml.py` owns duplicate-part, encrypted-entry, entry-count,
uncompressed-size, required-part, and per-part limits. DOCX and PPTX use it;
XLSX can reuse it in phase 5. The compressed artifact cap alone does not stop a
ZIP bomb or two duplicate XML parts being interpreted differently.

### 2.3 Skill packaging

The Dockerfile replaces every directory under `docker/sandbox/skills/` in one
layer and removes inherited script directories. The live contract derives its
expected skill names from that repo directory, so phase 5 does not edit either
place.

---

## 3. PPTX adapter

`formats/pptx.py` checks facts OOXML can answer reliably:

- package and presentation parts exist;
- the presentation-wide `p:sldSz` is positive;
- slide order resolves through relationships and produces the exact count;
- hidden slides are rejected because LibreOffice omits them from the preview,
  which would leave delivered content unverified;
- each slide has a drawable shape;
- shape extents are positive and no shape lies entirely off-canvas (partial
  edge bleed is allowed and clipping remains visual);
- picture crop values are within 0–100%;
- embedded-image relationships resolve to existing media.

The adapter does **not** claim to calculate rendered text overflow. OOXML stores
requested autofit, not the layout result, and has no font metrics or line
breaking. Overflow remains a rendered vision finding. Empty placeholders are
often intentional, picture extent is its frame, and slide size is one
presentation-wide value, so the earlier checks for empty placeholders, images
outside a second frame, and inconsistent per-slide dimensions were removed as
unrepresentable or false-positive-prone.

The adapter registers:

- suffix `.pptx`;
- canonical MIME
  `application/vnd.openxmlformats-officedocument.presentationml.presentation`;
- PDF conversion;
- `rendered_min_chars=0`;
- exact page-count matching;
- slide-specific visual framing.

---

## 4. Skill, routing, and rendering

`docker/sandbox/skills/pptx/SKILL.md` uses preinstalled `python-pptx`, one
deliverable-derived `.py`/`.pptx` stem, a consistent 16:9 layout by default,
explicit font and text budgets, bounded image geometry, no hidden slides, one
repair attempt, and source copy-back on revision.

Generation is incremental in source with local assertions, but verification
runs once over the complete deck. Verifying after every slide would reconvert,
rasterize, and review the entire prefix repeatedly — quadratic spend until the
content-addressed skip deferred in master spec §12 exists.

PPTX is an independent document-artifact path. PowerPoint, `.pptx`, slides, and
slide-deck requests load the PPTX skill and run generate → verify → save.
No PPTX code or dependency remains in the video-media implementation: the old
DOM exporter, UI, helper, declaration, and `dom-to-pptx` package are deleted.
The video pipeline remains a separate media generator with no PPTX behavior.

The PPTX MIME maps to the existing `PdfPreviewViewer`; the panel downloads the
real `.pptx`, while the viewer displays the receipt-bound PDF preview.

---

## 5. Checks and evidence

- Adapter unit fixtures cover clean decks, count, missing/duplicate/encrypted
  parts, zero slides, dangling slide/media relationships, hidden and empty
  slides, geometry, extent, and crop defects.
- Service tests prove the ceiling runs before conversion and a dropped converted
  page produces no receipt.
- Vision tests prove document and slide framing share one verdict contract.
- The office artifact integration test is parameterized over DOCX and PPTX and
  proves create, stale-receipt refusal, preview/source roles, later-turn source
  loading, in-place revision, stable source naming, and blob purge.
- The live OpenSandbox test generates with real `python-pptx`, converts through
  real LibreOffice, rasterizes through Poppler, issues a real receipt, and reads
  the presentationml MIME from the same bytes.

## 6. Exit criteria

1. PPTX generates, verifies, persists, renders through `PdfPreviewViewer`, and
   downloads as the real deck.
2. A conversion that drops a slide fails; an over-ceiling deck fails before
   LibreOffice runs.
3. Plain slide-deck requests route to the PPTX artifact skill.
4. Video-media code contains no PPTX exports, references, or dependencies.
5. Phase 5 needs no Dockerfile, roster-regex, or office integration-test shape
   change to install and exercise its skill.
