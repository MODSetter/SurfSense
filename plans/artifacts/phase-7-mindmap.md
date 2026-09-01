# Phase 7 — Interactive Mind-Map Artifacts

**Status:** Complete.
**Parent spec:** [`artifacts-overhaul.md`](./artifacts-overhaul.md).
**Depends on:** phase 1 foundation, phase 3 verification receipts, phase 5 programmatic-verification precedent, and the artifact-panel path used by phase 6.
**Independent of:** phase 10 public access. Phase 7 ships the authenticated
viewer and download; the same viewer becomes public only after phase 10
provides token-scoped manifests and files.

## 1. Goal

Add generated hierarchical mind maps as first-class artifacts. A mind map uses
the existing document-backed artifact model, renders interactively in the
right-hand artifact panel through Markmap, and downloads as a static PNG.

The user-visible contract is:

- the panel supports pan, zoom, fit, and branch collapse/expand;
- the download button returns `<title>.png`, never Markdown or HTML;
- the PNG is a static capture of the same default Markmap rendering users see
  in the panel, not a separately designed image;
- the artifact remains searchable and citable through its ordinary document;
- create and revise bind the Markdown used by the interactive viewer to the PNG
  produced from it, so the panel and download cannot silently diverge.

This phase adds one format adapter, one deterministic PNG render harness, one
format-aware panel viewer, and one sandbox skill. It does not add another
artifact model, API family, panel, editor, graph database, or export service.

## 2. Product and scope decisions

### 2.1 Canonical and downloadable representations

One artifact has two durable representations with different jobs:

1. `Document.source_markdown` / `markdown_representation` is the canonical
   semantic source. The same Markdown drives Markmap in the panel and supplies
   KB indexing, search, citations, accessibility, and revision context.
2. The primary `ArtifactFile` is a deterministic PNG rendered from that exact
   Markdown. It is the only user download.

The Markdown is not offered as a download. The PNG is not parsed back into a
mind map and is never the revision source.

### 2.2 Initial mind-map profile

Phase 7 supports generated, read-only, hierarchical maps. It intentionally does
not support:

- free-form graphs or multiple parents;
- manual node positions;
- in-panel text editing, node creation, drag/drop, or reconnection;
- per-node images, arbitrary HTML, remote assets, scripts, or embedded iframes;
- persisted collapsed state or per-user viewport state;
- SVG, HTML, PDF, or JSON downloads;
- reconstructing Markdown from the PNG with vision.

These exclusions keep Markdown a sufficient canonical model. A versioned graph
schema becomes justified only when editing, arbitrary relationships, positions,
or rich node metadata are real requirements. React Flow is therefore out of
scope; Markmap is the smaller library for the hierarchy that exists now.

Phase 7 also does not introduce a SurfSense mind-map theme. Node colors, link
colors, typography, spacing, shapes, and other map visuals come from Markmap's
built-in styles and default options. SurfSense supplies only the host container,
panel controls, and capture dimensions required to run the renderer.

## 3. Persistence and format identity

A mind map is:

- one `Document(document_type=ARTIFACT)` containing canonical Markmap Markdown;
- one `Artifact(format="mindmap")`;
- one primary `<slug>.png` file with MIME `image/png`;
- no preview file.

`ArtifactFormat` may add `MINDMAP = "mindmap"` for typed callers and roster
clarity. The database column remains a string. The manifest shape, blob model,
download route, indexing pipeline, citations, deletion, and optimistic revision
contract do not change.

Semantic identity is explicit rather than encoded in the filename.
`verify_artifact(format="mindmap", ...)`, the signed receipt,
`Artifact.format`, and the manifest carry that identity. The `.png` extension
and `image/png` MIME describe only the physical primary file. This keeps
mind-map PNGs distinct from generated-image PNGs without compound-suffix
dispatch.

## 4. Canonical Markdown contract

The source is a constrained Markdown hierarchy accepted by Markmap:

```markdown
# Product launch

- Research
  - Customers
  - Competitors
- Delivery
  - Backend
  - Frontend
```

The format checker shared by creation verification and focused unit tests
enforces:

- exactly one non-empty root heading;
- at least one child node;
- nested unordered-list hierarchy below the root;
- no skipped nesting level or empty label;
- bounded node count, depth, and label length;
- no raw HTML, images, fenced code, tables, directives, or remote assets;
- no control characters other than ordinary whitespace;
- UTF-8 input and normalized line endings.

Inline emphasis and code may be allowed only if the chosen Markmap
configuration renders them without enabling raw HTML. Links are plain text in
phase 7: the panel must not create navigable anchors from artifact content.

Limits belong in one backend module and are mirrored in the sandbox skill and
render-harness tests. Start conservatively at 60 nodes, depth 6, and 120
characters per label; increase only with readability evidence from the fixed
PNG canvas and the 640px panel. Over-limit maps fail with an instruction to
split or simplify the map rather than shrinking text until it is unreadable.

## 5. Deterministic PNG render harness

Markmap does not provide an official PNG export API. It renders an SVG DOM, so
phase 7 captures that DOM through the Chromium already installed for the
Remotion sandbox rather than serializing Markmap's `foreignObject` SVG or
adding a second browser installation.

### 5.1 Installed dependencies

Add `markmap-lib` and `markmap-view` to:

- `surfsense_web`, for the interactive panel renderer;
- the existing sandbox Remotion package, for deterministic still rendering.

Both lockfiles must resolve the same Markmap versions. Do not use a CDN,
`markmap-cli`, or runtime package installation. The CLI's supported standalone
output is HTML, while the product decision is PNG. Do not fork, copy, or
override Markmap's visual CSS.

### 5.2 Harness

Add a dedicated mind-map still composition and command under the existing
`/opt/remotion` render harness. The composition:

1. receives canonical Markdown through an input file/props contract;
2. parses it with `markmap-lib`;
3. renders it with `markmap-view`;
4. waits for fonts and layout;
5. expands all nodes and fits the complete map;
6. signals readiness only after the SVG has finite, non-empty bounds;
7. renders one PNG still through Remotion's managed Chromium.

The export is deterministic:

- fixed 2400×1600 output;
- no network access or remote assets;
- Markmap's built-in stylesheet and default visual options only;
- the browser's ordinary opaque page background, with no custom export theme;
- all branches expanded;
- no toolbar or interaction chrome in the PNG;
- output path supplied by the caller and ending in `.png`.

The harness exits non-zero for parse errors, missing nodes, non-finite geometry,
layout timeout, bounds outside the canvas, or a fitted scale below the readable
minimum. It writes no HTML or SVG deliverable.

The interactive viewer and PNG harness must use the same resolved Markmap
versions and the same rendering defaults. They may set only non-visual runtime
behavior required by the surface: container dimensions, all-expanded initial
state, fit, pan/zoom enablement, and reduced-motion duration. Do not add a
shared theme fixture because there is no SurfSense-authored theme.

“Same as the panel” means the PNG matches the panel's initial, all-expanded,
fitted Markmap appearance. It cannot include viewport changes a user makes
later, because the verified primary PNG is created before the user opens the
panel. Exporting the user's current zoom or collapsed state would require a
separate client-side export feature and is out of scope.

## 6. Verification and source binding

Mind maps use programmatic verification only:

```python
FormatAdapter(
    name="mindmap",
    suffix=".png",
    mime_type="image/png",
    convert_to_pdf=False,
    check=check_mindmap_png,
    requires_visual_review=False,
)
```

There is no PDF conversion, rasterization, vision-model review, or preview.
This is safe because the model authors bounded Markdown and trusted code
produces the pixels; the model never authors arbitrary PNG/SVG drawing bytes.

### 6.1 PNG checks

`check_mindmap_png` uses the installed image decoder to:

- require the PNG signature and successful full decode;
- reject truncated data and trailing-format confusion;
- require the exact export dimensions and an allowed color mode;
- enforce the existing byte limit plus a decoded-pixel ceiling;
- reject fully transparent, single-color, or effectively blank output;
- record useful non-blocking notes such as the dimensions.

The renderer owns visual layout checks before capture. Backend verification
does not attempt OCR or subjective aesthetic scoring.

### 6.2 Bind the viewer source to the download

The panel renders Markdown while the download serves PNG. A receipt that binds
only the PNG would permit those two durable representations to disagree.
Extend the verification receipt with an optional
`markdown_representation_sha256`:

1. `verify_artifact` accepts an optional `markdown_path`;
2. only adapters that declare representation binding may require it;
3. the mind-map verifier validates the Markdown profile and signs its hash
   together with the PNG hash;
4. `save_artifact` hashes the supplied `markdown_representation` and rejects a
   mismatch before persistence;
5. other formats omit the field and retain their current behavior.

The Markdown file remains transient sandbox input. Persisting its hash in the
signed receipt does not create a source-file blob or a new artifact role.
Receipt serialization, expiry, audience, and mutation checks remain shared.

The public tool call becomes:

```text
verify_artifact(
  path="/workspace/roadmap.png",
  format="mindmap",
  markdown_path="/workspace/roadmap.md"
)
```

followed by `save_artifact` with the exact contents of `roadmap.md` as
`markdown_representation`.

## 7. Generation skill and intent routing

Add `docker/sandbox/skills/mindmap/SKILL.md` and advertise `"mindmap"` through
`load_artifact_instructions`.

The skill teaches the agent to:

1. create one concise hierarchy in `/workspace/<slug>.md`;
2. validate it locally against the documented limits;
3. call the baked render command to create `<slug>.png`;
4. call `verify_artifact(path=..., format="mindmap", markdown_path=...)`;
5. fix all blocking findings in one pass and reverify once;
6. call `save_artifact` with the verified PNG and exact Markdown;
7. stop and explain a persistent blocker rather than looping.

The shared frontend-design guidance may inform content hierarchy and label
clarity, but it must not cause the agent to author CSS, colors, HTML, SVG, or
renderer options. The mind-map skill owns only map-specific content mechanics:
short labels, balanced branches, useful grouping, bounded depth, and no
paragraph-shaped nodes. The agent authors Markdown, not the visual design.

Intent routing adds a mind-map branch ahead of generic PDF/HTML defaults.
Requests to “make a mind map,” “map this topic,” “show the concept hierarchy,”
or equivalent explicit hierarchical-visual intent select mindmap. General
diagrams, process flows, sequence diagrams, free-form canvases, interactive
calculators, reports, and presentations retain their existing formats.

## 8. Right-panel renderer

### 8.1 Format-level dispatch

The current artifact panel selects file viewers by primary MIME. That is
insufficient here: the primary is `image/png`, but the panel must render the
canonical Markdown interactively.

Add a minimal artifact-format viewer seam ahead of primary-MIME dispatch:

```text
manifest.format == "mindmap"
  -> MindMapViewer(markdown_representation)
otherwise
  -> existing no-primary / MIME viewer behavior
```

The seam belongs in `features/artifacts`, not the generic file-viewer registry,
because it consumes the whole artifact manifest rather than a file. Do not
teach the generic image viewer that `image/png` means mindmap.

### 8.2 `MindMapViewer`

`MindMapViewer` is a client-only dynamic import. It:

- transforms `markdown_representation` with `markmap-lib`;
- renders into an owned SVG through `markmap-view`;
- uses Markmap's built-in stylesheet and default visual options without
  SurfSense-authored node, link, color, spacing, typography, or background
  overrides;
- enables pan, wheel/pinch zoom, and branch collapse/expand;
- supplies fit/reset controls through the panel's existing
  `zoomControlsContainer`;
- fits on first render and observes container resize without resetting a user's
  viewport after every resize;
- respects reduced motion by setting Markmap animation duration to zero;
- cleans up observers, event handlers, and the Markmap instance on unmount;
- exposes an accessible textual fallback/tree for screen readers;
- falls back to the shared unviewable state on invalid source while preserving
  the PNG download button.

Artifact content is untrusted. Configure the transformer with raw HTML disabled,
reject unsupported Markdown constructs on the backend, produce no active links,
and never pass artifact strings to `dangerouslySetInnerHTML` outside Markmap's
bounded rendering contract.

The primary PNG is not fetched to render the panel. It remains available through
the ordinary artifact download action. Required host layout CSS may size and
contain the SVG, but it must not restyle Markmap nodes or links.

### 8.3 Metadata and chat behavior

`artifact-format-meta.ts` gains a `mindmap` entry with a mind-map/network icon,
label `Interactive`, detail label `Mind map`, group `Files`, and
`viewingMode: "viewer"`.

The save result carries `format="mindmap"` so chat artifact collection never
infers semantic identity from the `.png` filename.
Clicking the card opens the ordinary artifact tab. No inline chat renderer or
new panel state is introduced.

Mobile uses the existing artifact drawer and the same viewer. Touch pan/pinch
must be covered explicitly.

## 9. Download and serving contract

The existing stable artifact download route returns the primary
`<title>.png` with `Content-Disposition: attachment`. It never falls
back to the document Markdown because this artifact always has a primary file.

Immutable PNG content remains attachment-only under the current route policy;
the panel does not need to fetch it. `X-Content-Type-Options: nosniff` remains
present. Phase 7 adds no export endpoint, client-side canvas export, HTML
download, or temporary signed URL.

Public download and public interactive viewing remain phase 10 work. Phase 10
must include `mindmap` in its format-level viewer coverage and continue to serve
only the allowlisted primary PNG.

## 10. Revision

`load_artifact_for_revision(artifact_id)` restores:

- `context.md`, which is the canonical current mind-map source;
- `current.png`, for reference/download parity only;
- `revised.png` as the expected output path;
- the existing `artifact_id` and `expected_generation`.

The `mindmap` revision instruction is:

> Edit `markdown_path`, render it to `expected_output_path` with the mind-map
> harness, verify both paths together, and save with the returned artifact ID
> and generation. Do not edit or reconstruct the PNG.

Every revision regenerates the complete PNG from the revised Markdown. The
source-binding receipt prevents saving an old PNG with new Markdown or new PNG
with old Markdown. A stale generation fails without replacing either durable
representation.

## 11. Failure and operational behavior

- Markdown parse/limit failure: fail before browser rendering with actionable
  node/depth/label findings.
- Browser or layout timeout: return one stable render error; do not save.
- PNG decode/blank-image failure: fail verification; regenerate once.
- Receipt/source/primary hash mismatch: reject save as post-verification
  mutation.
- Frontend transform failure: show the unviewable state and preserve PNG
  download.
- Indexing failure: retain the saved artifact and PNG under the existing
  retryable document-status behavior.
- Markmap package upgrade: update frontend and sandbox lockfiles together and
  run golden structure plus browser/export regression tests.

Logs should include artifact format, render stage, node count, depth, output
dimensions, duration, and failure category, but never dump full user content.

## 12. Required checks

### 12.1 Markdown and rendering

- valid root-plus-list Markdown parses into the expected hierarchy;
- empty roots, multiple roots, skipped levels, unsupported constructs, excessive
  nodes/depth/label length, and raw HTML fail before rendering;
- the harness renders a representative shallow, deep, wide, CJK, and long-label
  fixture to exact-size PNGs;
- export fixtures use Markmap's built-in CSS and contain no custom map theme,
  color callback, line-width callback, or style override;
- no fixture requires network access;
- layout timeout, non-finite bounds, clipping, and unreadably small fit fail
  closed;
- repeated rendering of the same fixture has stable dimensions and structure;
  byte identity is not required if Chromium metadata differs.

### 12.2 Verification and persistence

- explicit `format="mindmap"` selects the mindmap adapter for a `.png`, while
  `format="image"` remains the semantic identity for generated images;
- a valid PNG records `visual="not_required"`, no preview, and both primary and
  Markdown hashes;
- corrupt, truncated, wrong-size, oversized, transparent, and blank PNGs fail;
- changing either file after verification causes save to fail;
- save creates one document, one `Artifact(format="mindmap")`, and one
  `image/png` primary;
- manifest exposes Markdown plus the PNG primary; download returns PNG bytes and
  a safe `.png` filename;
- revision preserves the physical `.png` suffix, replaces both representations
  atomically, increments generation, and purges the superseded PNG blob.

### 12.3 Frontend

- format metadata reports `viewer` and the expected labels;
- format-level dispatch wins over the primary `image/png` MIME;
- panel and PNG use the same Markmap version and default visual configuration;
- pan, zoom, fit, branch toggle, resize, reduced motion, and
  unmount cleanup work in the desktop panel;
- mobile drawer supports touch pan/pinch and fit;
- malformed source shows the shared fallback with download preserved;
- the download button requests the artifact download route and receives PNG,
  never Markdown;
- screen readers receive the equivalent hierarchy without traversing an opaque
  visual-only SVG.

### 12.4 Routing and regression

- explicit and synonymous mind-map prompts load the mindmap skill;
- flowcharts and interactive calculators do not route to mindmap;
- roster and revision instructions advertise the new format;
- PDF, DOCX, PPTX, XLSX, HTML, Markdown, media, and unknown-format behavior
  remains green;
- phase 8 flashcards cannot classify generic JSON or image content as mindmaps;
- phase 10 public/fallback work cannot classify unrelated PNGs as mindmaps.

## 13. Delivery order

1. Add the constrained Markdown parser/checker and deterministic render-harness
   fixtures.
2. Add explicit format adapter selection, the mindmap PNG adapter, optional
   Markdown-hash receipt binding, and focused verification tests.
3. Add the sandbox skill, baked render command, intent routing, roster entry,
   and one sandbox-to-save integration.
4. Add format-level panel dispatch, the lazy Markmap viewer, controls,
   accessibility fallback, and format metadata.
5. Add revision restoration/instructions, hash-mismatch coverage, blob purge,
   and browser tests.
6. Run cross-format regression and update the authoritative artifact plan.

Each step keeps persistence, manifests, downloads, indexing, and panel state
format-blind. If implementation needs a mindmap-specific route or database
column, stop and repair the adapter/viewer boundary instead.

## 14. Exit criteria

1. Mind-map intent generates bounded canonical Markdown and a deterministic,
   verified `.png` with explicit `format="mindmap"` and no vision review.
2. The signed receipt binds the exact Markdown used by the panel to the exact
   PNG returned by download.
3. Save and revision use the existing document-backed artifact model,
   optimistic generation check, blob lifecycle, indexing, search, and citations.
4. The authenticated right panel renders the Markdown interactively with
   Markmap and supports pan, zoom, fit, and branch collapse/expand.
5. The ordinary download route returns only the primary PNG, captured from the
   same default Markmap rendering used by the panel; no custom map theme,
   Markdown, HTML, SVG, JSON, or generation source is user-downloadable.
6. Invalid, oversized, unsafe, unreadable, or mismatched maps fail before
   persistence, and frontend failures retain the verified PNG escape hatch.
7. No mindmap-specific persistence schema, API route, panel state, search path,
   citation kind, or editor path exists.
8. Existing artifact formats, phase 8 flashcards, and phase 10
   public/fallback assumptions remain green.
