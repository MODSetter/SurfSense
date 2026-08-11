# Phase 3 — `docx` skill

**Parent spec:** [`artifacts-overhaul.md`](./artifacts-overhaul.md) (§7.1 skills, §8 rendering).
**Depends on:** phase 2 complete (sandbox live, `pdf` skill shipped, binary `save_artifact` path proven, `preview_path` already accepted by the tool). The verification-loop mechanism — its contract, the tool-level input limits, and step rendering — is phase 2 §2.6; this phase adds a format skill that uses it and builds none of it.
**Goal:** Word documents, verified, plus the preview-PDF pairing that phase 4 inherits rather than reinvents.
**Ships to users:** "make me a Word doc" produces a real `.docx` with an inline preview.

---

## 1. Scope

In: the `docx` skill, the first live use of the `role=preview` file, and `PdfPreviewViewer` with its docx registry entry. The conventions the next two phases build on are master spec §7.1's (§2.1).

Out: `pptx` (phase 4), `xlsx` and the unviewable/download-card polish (phase 5), any deletion (phase 6).

**This is the first of three format phases (3 docx → 4 pptx → 5 xlsx).** Only phase 4's dependency on this one is real — it reuses `PdfPreviewViewer` and the preview pairing proven here. Phase 5 depends on nothing but phase 2 and is sequenced last because it carries the cumulative gates (all four formats, a clean legacy-tool roster) that clear phase 6.

---

## 2. Tasks

### 2.1 Skill conventions — master spec §7.1, not this file

The conventions every skill obeys (shape and scripts layout, the `SURFSENSE_VERIFIED:` sentinel that claims a verification, the two-hop freshness rule, `soffice`'s three requirements, deliverable-named output files) live in **master spec §7.1**, where phases 4 and 5 already look for skills. They are written once there because they are the same rule for three formats — a copy per phase file is three copies to keep in agreement, and this phase happens to be first, not authoritative. What phase 3 owes them is their first office-format exercise: docx is the first skill with a conversion hop, so it is the first place the sentinel and the two-hop rule are load-bearing rather than theoretical.

Revision costs these skills nothing to support — each already writes a generate script, that script is what `source_path` stores, and editing it back is the same operation whether it produces a workbook or a deck.

**One retroactive fix, and it is this phase's:** the shipped `pdf` skill still names its output `out.pdf` — threaded through `docker/sandbox/skills/pdf/SKILL.md`'s steps, its script invocations and defaults, and its `save_artifact` call — so every PDF a user has downloaded so far arrived as `out.pdf`. Rename it to a deliverable-derived stem per master spec §7.1 while the docx skill is being written, not afterwards: this is the only part of the filename convention that changes what users already receive, and two skills disagreeing about their own output naming is how a convention quietly becomes advice.

### 2.2 Skill — `docx`

Create with `docx` (npm, Node; preinstalled — instruct `require('docx')` directly, never `npm install`). Body encodes the known footguns (from Anthropic's publicly documented toolchain, authored fresh):

- US Letter vs A4 default; DXA page dimensions
- One page setup for the entire document — a single page size, portrait, no section break that changes either — as a **strong default the user can override by asking**. Content too wide for portrait is narrowed (column widths, font size) rather than rotated on the skill's own initiative, because genuinely wide tabular data is an xlsx and a silently landscaped page is usually a layout failure wearing a workaround. "Make it landscape" is a legitimate instruction and the skill obeys it; nothing downstream cares, since each rendered page is inspected on its own terms
- Tables: `columnWidths` **and** per-cell `width`, both `WidthType.DXA` (PERCENTAGE breaks in Google Docs); shading `ShadingType.CLEAR` never `SOLID`
- Lists via `numbering` config + `LevelFormat.BULLET`, never literal `•`
- `PageBreak` inside a `Paragraph`; separate `Paragraph`s, never `\n`
- **No table of contents unless the user asks for one.** A freshly generated docx TOC carries no page numbers until a field update, and `soffice --headless --convert-to pdf` does not update fields — so the preview PDF the loop inspects, and the one the user then sees in the panel, shows an empty or placeholder TOC. The verification loop would correctly report a defect that nothing in the `docx` API can fix from inside the sandbox. When the user does ask, emit it, keep the footgun below, and say plainly that page numbers fill in when Word opens the file
- A TOC that is asked for requires built-in `HeadingLevel.*` or explicit `outlineLevel`
- Right-aligned-on-same-line via right tab stop (**not** `PositionalTab` — renders as a small gap in LibreOffice, which is what our preview and verification see)
- Verify: the phase 2 §2.6 loop unchanged — measurable checks, `soffice --headless --convert-to pdf`, `pdftoppm`, then `inspect_sandbox_images` over every page and again with `mode="together"`. A docx reflows like a PDF, so it is generated whole, never page by page. The conversion hop is this skill's own script and carries master spec §7.1's requirements in full: private `-env:UserInstallation` profile, explicit `--outdir`, stale PDF and page renders deleted before regenerating, and the new PDF asserted non-empty and newer than the `.docx`. Skipping that last check is how the loop ends up inspecting the previous generation's pages while the gate reports everything current
- Save: `save_artifact(path=<deliverable>.docx, source_path=<deliverable>.js, preview_path=<deliverable>.pdf, …)` — one deliverable-derived stem for all three files, never `out.*`, because the basename is the download name the user gets (master spec §7.1)

### 2.3 Frontend — rendering

- `PdfPreviewViewer`: a thin wrapper around the existing `pdf-viewer.tsx` (relocated in phase 2) pointed at the **preview** file's `content_url`, registered for the docx MIME type. No download action inside the viewer — the panel header already serves the primary file (master spec §8.1). It differs from `PdfFileViewer` only in which file's URL it renders, which is why phase 4 adds pptx as a registry line and no component.
- No per-format work on the in-chat card or the unviewable state: both derive their label from the filename extension, so docx is covered the day the skill lands. The one branch that *is* new is the preview-absent fall-through (master spec §8.2/§8.3) — a docx whose `role=preview` file is missing renders the unviewable state rather than an empty viewer — and it lands here because this phase builds the component that needs it.
- Budget the verification honestly: `surfsense_web` has no component-test framework (master spec §8.3), so both branches of `PdfPreviewViewer` are checked by Playwright or by opening the panel. Neither is a few lines of unit test, and planning them as if they were is how the preview-absent branch ends up shipped unexercised.

### 2.4 Prompt & routing

- Subagent prompt: genre → format guidance and the Level 1 roster gain the docx entry (prose documents, letters, anything the user names as Word). Forgetting the roster entry fails the phase 2 §2.6 check rather than shipping a skill nothing advertises.
- Streaming/tool-UI: nothing new (the generic `save_artifact` handler covers all formats by design).

### 2.5 Checks

- **Mocked-sandbox integration test** under `tests/integration/artifacts/`, in the same shape as the modules already there (real session, fake blob backend, the sandbox session stubbed): a docx save with primary + preview + source returns the master spec §3.1 payload with the right roles and `source` omitted from `editor-content`; the gate refuses a `.docx` whose mtime is newer than the last recorded verification and accepts it once re-verified; and a later-turn revise produces one document with the source read back rather than rebuilt. No sandbox and no model, so it runs in CI — which is what makes it a check rather than an intention. The one failure it cannot reach is the stale-intermediate case, which is why master spec §7.1 makes that a rule inside the skill rather than an assertion outside it.
- A live end-to-end run — real sandbox, real model, "make me a Word doc" through to a rendered panel — stays a manual exit-criteria walk-through (§3). Phase 2's §2.7 parameterized harness was specified but never built, so nothing here adds "one row" to it; if that harness is ever built it belongs outside CI, since it needs both a live sandbox and a live vision model.
- Preview pairing, exercised end to end for the first time: a docx artifact returns two files with roles `primary` and `preview` (plus `source`, omitted from the `editor-content` payload per phase 1 §2.5, shipped). Deleting the document purges both blobs — an assertion, not work: phase 1's `delete_row` correction already calls `purge_document_blobs()` and is tested; what is new here is that the artifact carries three blobs instead of one.

---

## 3. Exit criteria

1. `docx` generates, verifies, persists, renders in `PdfPreviewViewer`, and downloads the real `.docx` exactly per master spec §8.3.
2. The preview pairing holds: two blobs out, both purged on delete, and the source file never surfaces as a user download.
3. A later-turn revision edits the stored generate script in place — same `document_id`, no sibling document.
