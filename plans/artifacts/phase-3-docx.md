# Phase 3 — verification service + `docx`

**Status:** Complete (2026-08-12). Targeted unit/integration checks pass; the
rebuilt `surfsense-sandbox:dev` image has no PDF scripts, and a real npm-generated
DOCX completed LibreOffice conversion, rasterization, receipt issuance, and
OOXML MIME detection through the live OpenSandbox service.
**Parent spec:** [`artifacts-overhaul.md`](./artifacts-overhaul.md) (§6.3 the verification loop, §7.1 skills, §8 rendering).
**Depends on:** phase 2 complete (sandbox live, `pdf` skill shipped, binary `save_artifact` path proven, `preview_path` already accepted by the tool).
**Goal:** move the verification loop out of the model's hands and into a backend service (`verify_artifact`), migrate `pdf` onto it, then add Word documents plus the preview-PDF pairing phase 4 inherits rather than reinvents.
**Ships to users:** "make me a Word doc" produces a real `.docx` with an inline preview, and every format's verification becomes a visible, stepwise thing instead of four tool calls the model has to sequence correctly.

---

## 1. Scope

**Why this phase grew.** Phase 2 shipped the loop as a procedure the model performs: a structural script that announces itself with a `SURFSENSE_VERIFIED:` line, a shell conversion, a rasterize, two `inspect_sandbox_images` calls, and a gate comparing mtimes against two ledger files. Docx is the first format with a conversion hop, and writing its skill against that design surfaced what the design costs: the middle hop can go stale (a failed reconvert leaves the previous generation's PDF for the model to inspect while every timestamp still lines up), the three rules that prevent it are prose asking each skill author to be careful identically, and none of it is testable without a live sandbox and a live vision model. Adding a second format to that shape means writing those rules a second time. Master spec §6.3 now puts the sequence in the backend instead, so this phase builds it once and docx becomes what phases 4 and 5 were always supposed to be: a body and an adapter.

**In:** the verification service and the `verify_artifact` tool; `pdf` migrated onto it; phase 2's sentinel, ledgers and `inspect_sandbox_images` deleted; then the `docx` skill, its structural adapter, the first live use of the `role=preview` file, `PdfPreviewViewer` with its docx registry entry, and adapter-owned canonical OOXML MIME.

**Out:** `pptx` (phase 4), `xlsx` and the unviewable/download-card polish (phase 5), legacy-system deletion (phase 6 — the deletions here are phase 2's own machinery, not `Report`/Typst).

**Two commits, in this order, each leaving the product working:**

- **3a — architecture, no new format.** The service ships, `pdf` verifies through it, the old machinery goes. Nothing user-visible changes except that verification reports progress; the exit gate is that a PDF still generates, verifies and saves with no skill scripts left in the image.
- **3b — docx on top of it.** Adapter (including canonical MIME), skill body, prompt entries, viewer and tests.

Splitting them is what makes a bisect meaningful: a PDF regression in 3a is the migration, and anything in 3b is the new format. Merging them would produce one commit where "the docx skill broke PDF" is a sentence someone has to debug.

**This is the first of three format phases (3 docx → 4 pptx → 5 xlsx).** Phase 4 depends on this one twice now — `PdfPreviewViewer` and the preview pairing proven here, and the service every later adapter registers with. Phase 5 still depends on nothing else and is sequenced last because it carries the cumulative gates that clear phase 6.

---

## 2. Tasks — 3a, the verification service

### 2.1 Layout

Under `app/artifacts/verification/`, beside the persistence service that consumes its receipts (`app/artifacts/service.py`):

| Module | Holds | Runs where |
|---|---|---|
| `formats/pdf.py` | Today's `check_pdf.py` as a pure function over PDF bytes: near-blank pages, page count, unembedded fonts | Backend, in-process (`pypdf` is already a dependency) |
| `formats/docx.py` | OOXML structural checks (3b, §3.1) | Backend, in-process (`zipfile` + `ElementTree`) |
| `render.py` | `soffice` conversion and `pdftoppm` rasterization into a per-verification build directory | Sandbox session, via `run_command` |
| `vision.py` | Contextual review of all pages in one bounded call or overlapping consecutive windows | Backend, `get_vision_llm()` |
| `receipt.py` | Sign, write, read, validate | Backend + one sandbox write |
| `service.py` | The orchestration and the progress events | Backend |

The split is not decoration: everything except `render.py` is a function over bytes or strings, so the whole of the format knowledge this phase adds is unit-testable without a sandbox — which is the property the shell-script design could not have at any price.

### 2.2 Structural checks move and become evidence-based

`docker/sandbox/skills/pdf/scripts/check_pdf.py` becomes `formats/pdf.py` with its interface inverted: it takes bytes and returns findings instead of printing them and exiting. The `SURFSENSE_VERIFIED:` line and argument parsing fall away. Near-blank pages, page count and fonts remain cheap hard checks. The nominal-margin check does not: a text coordinate inside a configured margin is not proof of clipping (running headers and footers belong there), so it produced false failures that pypdf cannot resolve. Clipping and overlap stay in the rendered visual review; the replacement behavior is fixed by a test proving a running header is structurally valid.

### 2.3 `render.py` — the hops the model no longer sequences

Per verification, a build directory created for that run alone (`/tmp/verify-<uuid>/`). Inside it:

- The primary bytes already read for structural checks are written under a fixed absolute snapshot name. Conversion and rasterization use only that snapshot, never the mutable workspace path; the snapshot and generated preview are rechecked before review, and the rendered images are read into backend memory before the vision calls.
- `soffice --headless --convert-to pdf` over the snapshot, with a private profile (`-env:UserInstallation=file:///tmp/soffice-<uuid>`) and an explicit `--outdir`, output existence and non-emptiness asserted afterwards — soffice exits 0 having produced nothing often enough that its status is not evidence.
- `pdftoppm -jpeg -r 100` into the same directory.
- Every path `shlex.quote`d. These commands are assembled from a filename the model chose, so the quoting is a trust boundary, not tidiness.

The fresh directory is what retires the two-hop rule: there is no previous output to mistake for this one, so nothing has to prove its evidence is current. It also bounds cleanup to one `rm -rf` the session can skip entirely without consequence, since sandboxes are reaped per thread.

### 2.4 `vision.py` — one contextual, severity-aware review

Rendered pages are reviewed as a flowing document, not once in isolation and then a second time for comparison. Up to the model's image ceiling is one call; longer documents use overlapping consecutive windows, and every page is still included. This removes duplicate calls for small documents and prevents normal page continuations or final-page whitespace from becoming isolated-page false positives. The parsed verdict has two channels: blocking findings for unusable/incomplete output, and advisory warnings for aesthetics. Warnings remain visible but do not suppress receipt issuance. Three constraints:

- Invoke through `invoke_json` (`utils/structured_output.py`) over the LLM's `ainvoke`, because `QuotaCheckedVisionLLM` meters `ainvoke` — a "cleaner" direct call to a provider SDK would silently stop billing hosted verification (master spec §12).
- Keep verification's own `usage_type`, so the spend stays attributable per master spec §12, and keep the credit-exhausted branch: it produces a receipt whose visual verdict is the reason there is none only when every completed call was clean. A known defect or non-quota inspection failure wins over a concurrent quota denial and produces no receipt.
- Bound automatic revision in the PDF/DOCX skills and deliverables prompt: fix blocking findings once, reverify, and report a remaining blocker instead of entering an open-ended rewrite loop. The backend still never signs a document with a blocking defect.

### 2.5 `receipt.py` — the gate contract

The payload and signing scheme are master spec §6.3. Implementation notes only:

- HMAC-SHA256 over a canonical JSON encoding, keyed by `SECRET_KEY`, in the shape `OAuthStateManager` already uses (`utils/oauth_security.py`) — the same two primitives, not a new crypto idea.
- The signed payload includes the workspace id and sandbox session id; `save_artifact` validates both, so a receipt and identical files copied from another sandbox cannot spend one workspace's verification and save in another.
- Written into the session at a fixed path so `save_artifact` needs no argument to find it. One receipt per session at a time: the model verifies, then saves, and a receipt for a file it abandoned is a receipt whose hashes no longer match anything being saved, which is the correct outcome for free.
- Short expiry, checked on read. Not for security — the signature does that — but so a receipt cannot outlive the sandbox state it describes on a session reused across turns.

### 2.6 `service.py` — the orchestration and its visibility

The five steps of master spec §6.3, in order, short-circuiting on the first failure that makes later steps meaningless (no findings, no conversion). A `verification_progress` custom event as each step begins, down the path `report_progress` and `scraper_progress` already use (`tasks/chat/streaming/handlers/custom_events.py`), which is what makes one long tool call legible and is the reason phase 2's objection to a single verification tool does not survive (parent spec §6.3, "One call, still visible"). The page ceiling is a config constant checked immediately before rasterizing, where every format has a page count; over it, the verification fails with a finding, never a truncation.

### 2.7 `verify_artifact` — the tool

One input (`path`), findings and the preview path out. Registered in the deliverables tool index and the shared catalog beside `save_artifact`, with a streaming emission handler and a frontend card in the same shape as the existing tool UIs — the card's job is to render the progress events and the verdict, so a user watching a verification sees the steps rather than a spinner.

### 2.8 `save_artifact` — the gate, rewritten

Replace the mtime-and-ledger check with: read the receipt, verify the signature and expiry, hash the primary bytes the tool is about to persist and compare against the receipt's, and do the same for the preview whenever the receipt names one. What must survive the rewrite is the "could not verify" branch — a receipt carrying a reason instead of a visual verdict still saves, with the reason recorded in `document_metadata`, because that path exists for a deployment with no vision model configured and for premium credit exhausted mid-loop, and turning either into a refusal discards a finished deliverable. What goes: `_VISUAL_SUFFIXES`, `_required_kind`, `_names_artifact`, and the suffix-versus-`mimetypes` reasoning that surrounded them — the receipt names its own format, so nothing in the gate has to infer one.

### 2.9 Deletions — 3a's, and they are not optional

Leaving either mechanism in place gives the gate two ways to pass, which is the one outcome worse than the design being replaced:

- `deliverables/tools/verification.py` (the ledgers, `VerificationKind`, `record_verification`, `check_verification`)
- The `_VERIFIED_SENTINEL` recording branch in `deliverables/tools/sandbox.py`
- `inspect_sandbox_images`, its catalog entry, its streaming handler (`handlers/tools/inspect_sandbox_images/`) and its frontend card
- `docker/sandbox/skills/pdf/scripts/` in full (`check_pdf.py`, `render_pages.sh`) — the image ships no skill scripts after this phase (master spec §7.2)
- The unit tests covering the sentinel, the ledgers and the vision tool, replaced by tests over the service's functions

`FakeSession` in `tests/unit/sandbox/test_deliverables_tools.py` is shared by the tests that survive and the tests being written, so it moves to `tests/utils/fake_sandbox.py` rather than being copied.

### 2.10 `pdf` SKILL.md — what a skill looks like afterwards

Authoring guidance for the format, then one `verify_artifact` call, at most one blocking-finding revision and re-verification, then `save_artifact`. The steps that go are the ones the service now owns: the `check_pdf.py` invocation, rasterization, and direct vision calls. The retroactive `out.pdf` → deliverable-derived rename (master spec §7.1) lands in the same edit, since it is the same file and the same convention.

**3a exit gate:** "create me a resume as a PDF" runs end to end with progress events, a signed receipt, and no scripts directory in the image; the gate refuses a save whose bytes changed after verification and accepts a byte-identical regeneration that the mtime comparison used to reject.

---

## 3. Tasks — 3b, `docx`

### 3.1 Structural adapter — `formats/docx.py`

The checks that read the OOXML directly, which is where a docx's defects actually live. A docx is a zip of XML, so this is `zipfile` + `ElementTree` and no new dependency: percentage table widths (`w:tblW`/`w:tcW` with `w:type="pct"`), shading set to `solid` instead of `clear`, literal bullet glyphs in paragraph text where numbering should be, tables with no grid, and a TOC field with no heading outline levels beneath it. Each is a defect the rendered page shows too — but showing it costs a vision call and names it vaguely ("this table looks wrong"), while the markup names it exactly and for free.

The adapter is also a parser trust boundary: reject duplicate OOXML part names, encrypted entries, excessive entry counts, and excessive per-part or aggregate uncompressed sizes from `ZipInfo` before reading XML. The compressed artifact-size ceiling alone does not stop a small ZIP bomb, and duplicate `word/document.xml` entries can make Python and LibreOffice inspect different content.

The adapter registers docx as a PDF-converting format, which is the whole of what the service needs to know about it: the conversion, the rasterize, the review, the ceiling and the receipt are all format-blind already.

### 3.2 Skill — `docx`

Create with `docx` (npm, Node; preinstalled — instruct `require('docx')` directly, never `npm install`). The body is authoring guidance and this phase's footgun list, followed only by the generic verify/save call and one-blocking-revision cap; it contains no conversion, rasterization, receipt, or revision-loading procedure (master spec §7.1):

- US Letter vs A4 default; DXA page dimensions
- One page setup for the entire document — a single page size, portrait, no section break that changes either — as a **strong default the user can override by asking**. Content too wide for portrait is narrowed (column widths, font size) rather than rotated on the skill's own initiative, because genuinely wide tabular data is an xlsx and a silently landscaped page is usually a layout failure wearing a workaround. "Make it landscape" is a legitimate instruction and the skill obeys it; nothing downstream cares, since each rendered page is inspected on its own terms
- Tables: `columnWidths` **and** per-cell `width`, both `WidthType.DXA` (PERCENTAGE breaks in Google Docs); shading `ShadingType.CLEAR` never `SOLID`
- Lists via `numbering` config + `LevelFormat.BULLET`, never literal `•`
- `PageBreak` inside a `Paragraph`; separate `Paragraph`s, never `\n`
- **No table of contents unless the user asks for one.** A freshly generated docx TOC carries no page numbers until a field update, and `soffice --headless --convert-to pdf` does not update fields — so the preview PDF the service inspects, and the one the user then sees in the panel, shows an empty or placeholder TOC. The verification would correctly report a defect that nothing in the `docx` API can fix from inside the sandbox. When the user does ask, emit it, keep the footgun below, and say plainly that page numbers fill in when Word opens the file
- A TOC that is asked for requires built-in `HeadingLevel.*` or explicit `outlineLevel`
- Right-aligned-on-same-line via right tab stop (**not** `PositionalTab` — renders as a small gap in LibreOffice, which is what our preview and verification see)
- A docx reflows like a PDF, so it is generated whole, never page by page
- Verify and save: `verify_artifact(<deliverable>.docx)`, then `save_artifact(path=<deliverable>.docx, source_path=<deliverable>.js, preview_path=<the returned preview>, …)` — one deliverable-derived stem, never `out.*`, because the basename is the download name the user gets (master spec §7.1)

### 3.3 MIME determinism

The DOCX format adapter owns the canonical OOXML wordprocessing MIME alongside its suffix, checker and conversion mode. `save_artifact` obtains the primary MIME from that adapter and requires the signed receipt to name the same format, rather than comparing `mimetypes` and libmagic strings. This matters beyond DOCX: host MIME tables vary, OOXML is truthfully sniffed as a ZIP container, and JavaScript alone has a current `text/javascript` name plus legacy libmagic aliases. A future PPTX or XLSX adapter supplies its canonical MIME in the same registry entry. Generation sources use their own role-specific `.py`/`.html`/`.js` allowlist and UTF-8/NUL validation because source text is stored for revision but never rendered or downloaded (master spec §8.2).

### 3.4 Frontend — rendering

- `PdfPreviewViewer`: a thin wrapper around the existing `pdf-viewer.tsx` (relocated in phase 2) pointed at the **preview** file's `content_url`, registered for the docx MIME type. No download action inside the viewer — the panel header already serves the primary file (master spec §8.1). It differs from `PdfFileViewer` only in which file's URL it renders, which is why phase 4 adds pptx as a registry line and no component.
- The preview-absent fall-through (master spec §8.2/§8.3) lands here because this phase builds the component that needs it. The gate makes it unreachable in practice now — an office format has no clean receipt without a preview, and a save whose receipt names one must present it — but the registry is a MIME-to-component map that cannot promise the file exists, and the alternative to the branch is an empty viewer over an artifact that downloads perfectly well.
- `UnviewableArtifact` and its message helper come out of `artifact-panel.tsx` as their own modules, because this is the second caller. The extraction is what keeps the two states identical rather than similar.
- No per-format work on the in-chat card: it derives its label from the filename extension, so docx is covered the day the skill lands.
- Budget the verification honestly: `surfsense_web` has no component-test framework (master spec §8.3), so both branches of `PdfPreviewViewer` are checked by Playwright or by opening the panel. Neither is a few lines of unit test, and planning them as if they were is how the preview-absent branch ends up shipped unexercised.

### 3.5 Prompt & routing

- Subagent prompt: the genre → format guidance and the Level 1 roster gain the docx entry (Word or `.docx` named by the user — prose still defaults to pdf, master spec §6.2). Forgetting the roster entry fails the installed-frontmatter check rather than shipping a skill nothing advertises; the roster's wording is itself a test contract, and master spec §7.1 names the two honest ways to write a two-format roster.
- Streaming/tool-UI: the generic `save_artifact` handler covers all formats by design; the only new surface is `verify_artifact`'s card from 3a.

### 3.6 Checks

- **Unit, and this is the point of the whole restructuring:** `formats/docx.py` against fixture bytes — a percentage-width table, `solid` shading, a literal `•`, a TOC without outline levels, and a clean document — plus `receipt.py` round-tripping sign/verify, rejecting a tampered payload, and rejecting an expired one. No sandbox, no model, no fixtures beyond a few small files.
- **Mocked-sandbox integration test** under `tests/integration/artifacts/`, in the shape of the modules already there (real session, fake blob backend, sandbox session stubbed): a docx save with primary + preview + source returns the master spec §3.1 payload with the right roles and `source` omitted from `editor-content`; the gate refuses bytes that do not match the receipt and accepts them once re-verified; a later-turn revise produces one document with the source read back rather than rebuilt, under a stable filename (master spec §7.1's compounding rule).
- **Live-sandbox check, small and specific:** generate a real docx with the npm `docx` package, verify it, and assert two things no mock can — that the receipt is real (soffice converted, pages rendered, hashes match) and that the stored MIME is the OOXML type rather than `application/zip`. Both are properties of the production image, and both fail silently everywhere else.
- A full live end-to-end run — real sandbox, real model, "make me a Word doc" through to a rendered panel — stays a manual exit-criteria walk-through (§4). Phase 2's parameterized harness was specified but never built, so nothing here adds "one row" to it; if it is ever built it belongs outside CI, since it needs both a live sandbox and a live vision model.
- Preview pairing, exercised end to end for the first time: a docx artifact returns two files with roles `primary` and `preview` (plus `source`, omitted from the `editor-content` payload per phase 1 §2.5, shipped). Deleting the document purges every blob — an assertion, not work: phase 1's `delete_row` correction already calls `purge_document_blobs()` and is tested; what is new is that the artifact carries three blobs instead of one.

---

## 4. Exit criteria

1. **3a:** PDF generates, verifies through `verify_artifact` and saves, with progress events visible, a signed receipt behind the save, and no `scripts/` directory left in the sandbox image. No path can pass the gate without a receipt.
2. `docx` generates, verifies, persists, renders in `PdfPreviewViewer`, and downloads the real `.docx` exactly per master spec §8.3 — with the OOXML MIME stored, proven on the production image.
3. The preview pairing holds: two blobs out plus the source, all purged on delete, and the source never surfaces as a user download.
4. A later-turn revision edits the stored generate script in place — same `document_id`, no sibling document, no compounding filename.
5. Adding `pptx` in phase 4 is one adapter, one skill body, one registry line and one test case. If it looks like more than that, this phase left something in the wrong place.
