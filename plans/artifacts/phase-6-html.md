# Phase 6 — Interactive HTML Artifacts

**Status:** Complete.
**Parent spec:** [`artifacts-overhaul.md`](./artifacts-overhaul.md).
**Depends on:** phase 1 foundation (schema, storage, panel, manifest), phase 3 verification service, and the phase 5 programmatic-verification precedent.
**Independent of:** phase 9. Authenticated HTML rendering needs nothing from the public path; public HTML sharing is gated on phase 9 route hardening (§9).

## 1. Goal

Add interactive, self-contained HTML as a first-class artifact format that renders in the existing right-hand artifact panel, without a schema, persistence, or API change. HTML is a new adapter plus a new viewer, exactly as invariant §12.12 requires. It is not a new artifact domain, panel, or route.

The deliverable is a single self-contained page — inline CSS, inline JavaScript, browser-local state — of the kind an "interactive pricing calculator" or dashboard prompt produces. The reference output is [`html-artifacts.md`](../../html-artifacts.md).

## 2. Scope

In:

- an `.html` structural `FormatAdapter` with MIME `text/html`;
- a sandbox HTML authoring skill (mechanics), and a shared design skill it defers to for aesthetics;
- intent-based routing so interactive requests select HTML without the user naming a format;
- programmatic verification: no conversion, rasterization, vision review, or preview file;
- primary-only persistence through the existing artifact service;
- a sandboxed-iframe viewer in the artifact panel, keyed off `text/html`;
- HTML revision instructions and format metadata;
- backend and browser coverage.

Out:

- public artifact viewing of HTML (deferred to the phase 9 public path, see §9);
- inline chat-card execution of HTML (panel-only; a card is a later option);
- server-side HTML rendering, screenshotting, or PDF preview generation;
- external application code, backends, or persisted state inside an artifact;
- editing an HTML artifact in the document editor (artifacts stay read-only, invariant §12.10).

## 3. Persistence

An HTML artifact is one `Document(document_type=ARTIFACT)` plus one `Artifact(format="html")`. Its files are:

- a primary `.html` file with MIME `text/html`;
- no preview.

`Artifact.format` remains an adapter-owned string (`enums.py` may add `HTML = "html"` for roster clarity only; it is not a database enum and nothing branches on it). The document owns searchable Markdown under `/documents/` and follows ordinary chunking, indexing, search, move, rename, and deletion. `save_artifact`, `service.py`, `storage.py`, and the artifact routes are already format-blind and require no change.

HTML requires no migration, document subtype, chunk table, search branch, or format-specific route.

## 4. Verification

The `.html` adapter is registered in `verification/formats/registry.py::_ADAPTERS` as:

```
FormatAdapter(
    name="html",
    suffix=".html",
    mime_type="text/html",
    convert_to_pdf=False,
    check=check_html,
    requires_visual_review=False,
)
```

`convert_to_pdf=False` and `requires_visual_review=False` keep HTML out of the conversion, rasterization, and vision paths, matching XLSX. A successful receipt records `visual="not_required"` and binds the primary hash; it has no page count, preview path, or preview hash.

`check_html(data: bytes) -> StructuralCheckResult` in `verification/formats/html.py` is deliberately thin, because the render-time sandbox (§6) is the real trust boundary, not the verifier. It:

- decodes the bytes as UTF-8 and rejects non-decodable input (blocking finding);
- rejects empty or whitespace-only content (blocking finding);
- confirms the payload parses as HTML markup (blocking finding on unparseable input);
- enforces the **fragment contract** — the payload must not contain a `<!DOCTYPE>`, `<html>`, `<head>`, or `<body>` wrapper (blocking finding). A fragment guarantees the viewer's document shell, and therefore its Content-Security-Policy, is always authoritative (§6);
- emits an **advisory** note (never a blocker) for any external resource reference (`<script src>`, `<link href>`, `@import`, `src=`/`href=` to an off-origin URL) outside the font allowlist, since the render-time CSP will silently drop those resources.

Size stays bounded by the existing `ARTIFACT_MAX_FILE_BYTES` limit enforced in save, verify, sandbox read, and revision load. HTML introduces no second limit.

Verification never rewrites or "sanitizes" the bytes. What the agent authored is what the viewer renders, under sandbox constraints.

## 5. Generation skill

Two layers author an HTML artifact, and they must stay separate: the **format skill** owns mechanics, and a **shared design skill** owns aesthetics. The HTML skill does not re-teach visual design; it defers to the design skill so PPTX, PDF, DOCX, and image generation can reuse the same design core rather than each carrying its own copy.

### 5.1 HTML format skill (mechanics)

`docker/sandbox/skills/html/SKILL.md` teaches the deliverables agent to author one self-contained interactive HTML **fragment** in `/workspace`, following the reference in `html-artifacts.md`:

- emit a fragment only — no `<!DOCTYPE>`, `<html>`, `<head>`, or `<body>` wrapper; the panel wraps it in a shell (§6);
- inline all CSS in a `<style>` block and all behavior in an inline `<script>`; do not fetch application code or link external stylesheets;
- keep all state in the page (in-memory or the browser's own storage inside the sandbox); the page has no backend and must not call app APIs;
- the only permitted external resources are Google Fonts (`fonts.googleapis.com`, `fonts.gstatic.com`); embed images as `data:` URIs; anything else will be dropped by the render-time CSP;
- build for keyboard and screen-reader use (labels, roles, `:focus-visible`), matching the reference;
- never install or download dependencies in the sandbox.

The generation flow mirrors the other skills:

1. author the fragment at an output path in the sandbox;
2. call `verify_artifact(path=output_path, format="html")` — structural only, warnings advisory; fix all blockers together, regenerate once, reverify, and stop with an explanation rather than looping;
3. call `save_artifact(path=output_path, title="...", markdown_representation="...")`.

The Markdown representation summarizes the artifact's purpose, its interactive controls, and its key content for search and accessibility — not the raw HTML.

### 5.2 Shared design skill (aesthetics)

Visual quality is not duplicated across format skills.
`docker/sandbox/skills/frontend-design/DESIGN.md` supplies general design
guidance — subject grounding, a named palette, deliberate
type pairing and scale, structural hierarchy, restraint, and copywriting.
HTML keeps its web-only addendum (layout, motion, CSS specificity, responsive
behavior, and reduced motion) in `html/SKILL.md`; other formats retain their
own medium-specific rules.

Because `load_artifact_instructions` simply `cat`s one
`/opt/skills/<name>/SKILL.md`, the Docker skills-assembly step appends the
shared guidance to every installed format `SKILL.md`. The `frontend-design` folder
contains `DESIGN.md`, not `SKILL.md`, so it is neither advertised as an
artifact format nor copied into `/opt/skills`. This also avoids replacing the
base image's unrelated `frontend-design` skill.

### 5.3 Intent routing — the user never has to say "HTML"

Interactive intent, not the literal word "HTML", selects this format. `Create an interactive pricing calculator` produces an HTML artifact with no format hint from the user; this is the defining behavior of the format, matching the reference in `html-artifacts.md`.

The deliverables `system_prompt.md` format policy currently ends with "otherwise, prefer PDF for a finished deliverable," which would swallow interactive requests into a static PDF. Phase 6 inserts an **interactive-intent branch ahead of that PDF default**: a request whose deliverable is something the user operates rather than reads — a calculator, configurator, estimator, simulator, interactive dashboard, live/interactive prototype, widget, or tool with controls — routes to HTML. The signal is interactivity (inputs, sliders, toggles, live-updating output), not the noun. A request for a static write-up, letter, report, deck, or sheet keeps its existing format; an explicit format request still overrides, as it does today.

`description.md` advertises the interactive capability so the supervisor delegates these requests to the deliverables agent. `load_artifact_instructions`' format `Literal` in `tools/sandbox.py` gains `"html"`, and the roster test (`tests/unit/sandbox/test_deliverables_skill_roster.py`) is updated so the installed HTML skill is advertised. A routing test asserts that an interactive prompt with no format word selects HTML and does not fall through to PDF.

## 6. Sandboxed viewer and security model

HTML artifacts are untrusted, agent-authored code that executes in the viewer's browser. The entire security posture is: **never render artifact HTML on the SurfSense origin, and never grant the frame same-origin power.** Two rules, one boundary.

### 6.1 Backend: attachment-only, always

`text/html` must never be added to `_is_inline` in `document_files_routes.py` (or the artifact content route that reuses it). Stored HTML is served with `Content-Disposition: attachment` and `X-Content-Type-Options: nosniff`, so a direct hit on the content URL downloads a file and can never execute on our origin. A regression test asserts `text/html -> attachment`, alongside the existing PDF/MP4 inline cases.

### 6.2 Frontend: fetch as bytes, render in a sandboxed frame

The file-viewer registry (`features/file-viewers/viewer-registry.ts::FILE_VIEWERS`) maps `"text/html"` to a client-only `HtmlFileViewer`. Because `features/artifacts/viewer-registry.ts::VIEWERS` spreads `FILE_VIEWERS`, the artifact panel picks it up with no panel change. `HtmlFileViewer`:

- rejects oversized files before fetch and again before render, mirroring `XlsxViewer`;
- fetches the primary via the manifest `content_url` using the existing authenticated blob fetch (`download-file.ts`), so auth headers are sent and the frame never navigates the app to the content URL;
- wraps the fetched fragment in a document shell it controls, then renders it through the frame's `srcdoc` — never by setting `iframe.src` to the content URL;
- degrades a failed fetch, oversized payload, or decode error to the shared unviewable state while preserving the header download button.

### 6.3 The frame contract

The iframe is created with exactly:

```
sandbox="allow-scripts"
```

and nothing else. In particular it omits `allow-same-origin` (so the frame runs in an opaque origin with no access to parent DOM, cookies, `localStorage`, or the session), and omits `allow-forms`, `allow-popups`, `allow-popups-to-escape-sandbox`, `allow-modals`, `allow-downloads`, `allow-top-navigation`, and `allow-top-navigation-by-user-activation`. Scripts run; nothing escapes the frame.

### 6.4 The document shell and CSP

The viewer builds the shell so the fragment cannot supply its own `<head>`:

```html
<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="Content-Security-Policy" content="
      default-src 'none';
      script-src 'unsafe-inline';
      style-src 'unsafe-inline' https://fonts.googleapis.com;
      font-src https://fonts.gstatic.com;
      img-src data:;
      connect-src 'none';
      form-action 'none';
      base-uri 'none'">
  </head>
  <body><!-- agent fragment --></body>
</html>
```

`script-src 'unsafe-inline'` is safe here because the frame is an opaque origin with no same-origin capability; `connect-src 'none'` blocks `fetch`/XHR/WebSocket exfiltration; `img-src data:` forces images inline; the font directives allow only the Google Fonts pair the reference uses. The CSP is defense in depth layered on the sandbox attribute; the sandbox attribute is the primary control. The fragment contract (§4) exists precisely so this shell is always the one that runs.

All viewers remain read-only (overhaul §8). The frame is a preview surface, not an editor.

## 7. Revision

HTML uses the existing revision path with no contract change. `_REVISION_INSTRUCTIONS` in `tools/load_artifact_for_revision.py` gains an `"html"` entry:

> Edit `primary_path` directly, or regenerate the fragment from `markdown_path` plus the user's new instruction, and write the result to `expected_output_path`. Keep it a self-contained fragment. Do not reconstruct the page with vision.

`load_artifact_for_revision(artifact_id)` restores the current `.html` primary plus Markdown context and the current generation; the save passes `artifact_id + expected_generation`. A changed title, layout, or palette is still the same artifact unless the user asks for a separate copy.

## 8. Format metadata and routing

`features/artifacts/artifact-format-meta.ts` gains:

```
html: {
  icon: FileCode,          // already imported
  label: "Interactive",
  detailLabel: "HTML",
  groupKey: "files",
  groupLabel: "Files",
  viewingMode: "viewer",
}
```

`viewingMode: "viewer"` sends HTML to the right panel through `ArtifactViewerContent`, the same path as PDF and XLSX; `open-chat-artifact.ts` and `artifact-format-icon.tsx`/`artifact-format-label.tsx` work off this meta with no further change.

## 9. Public sharing boundary

Public HTML is out of this phase. The current public content route (`public_chat_routes.py::stream_public_artifact_file`) streams the stored MIME with no `Content-Disposition` and no `nosniff`, which phase 9 §7.1 already commits to fixing for all formats. HTML must not be publicly served until that hardening lands, because a public content URL that omits attachment/`nosniff` is a route to executing agent HTML on a shared origin.

When public HTML does ship, it reuses the same story: bytes fetched via the token-scoped content route (attachment + `nosniff`), rendered in the same sandboxed `srcdoc` frame. The phase 9 public viewer list gains an HTML entry at that point. No public artifact copy, no second render path.

## 10. Security invariants

1. `text/html` is never inline on any backend route; stored HTML is always an attachment with `X-Content-Type-Options: nosniff`.
2. Artifact HTML renders only inside an iframe whose `sandbox` is `allow-scripts` and nothing else; `allow-same-origin` is never present.
3. The frame is loaded from viewer-built `srcdoc`, never from `iframe.src` pointed at a content URL, and never through `dangerouslySetInnerHTML` in the React tree.
4. The agent emits a fragment; the viewer owns the document shell and its Content-Security-Policy, so page-supplied `<head>` content can never displace the CSP.
5. Verification neither rewrites nor sanitizes bytes; the sandbox and CSP are the trust boundary, and structural checks only fail closed on unusable input.
6. External network access from a rendered artifact is limited to the Google Fonts pair by CSP; `connect-src 'none'` blocks data exfiltration.

## 11. Required checks

### 11.1 Verification

- non-empty, UTF-8-decodable fragment verifies with `text/html` and `visual="not_required"`;
- empty, non-UTF-8, unparseable, and full-document (`<html>`/`<head>`/`<body>`/`<!DOCTYPE>`) payloads fail before persistence;
- off-allowlist external references produce advisory notes, not blockers;
- the receipt binds the primary hash and carries no rendered fields;
- oversized payloads fail on the existing size limit.

### 11.2 Persistence and revision

- save creates one document + one `Artifact(format="html")` + one primary file, no preview;
- the manifest exposes the primary with MIME `text/html` and a `content_url`;
- `load_artifact_for_revision` restores the current primary and Markdown; a stale `expected_generation` fails without touching files or generation;
- one sandbox-to-save integration authors a real fragment, verifies it, persists it, revises it, and confirms blob purge of the superseded generation.

### 11.3 Routing and serving

- an interactive prompt with no format word (e.g. "create an interactive pricing calculator") selects HTML and does not fall through to the PDF default;
- a static request (report, letter, deck, sheet) keeps its existing format, and an explicit format word still overrides;
- the installed HTML skill appears in the deliverables prompt (roster test);
- the authenticated content route serves `text/html` as `attachment` with `nosniff` (regression test beside the PDF/MP4 inline cases).

### 11.4 Browser

- the registry resolves `text/html` to `HtmlFileViewer`, and the meta reports `viewingMode: "viewer"`;
- the rendered iframe carries `sandbox="allow-scripts"` with no `allow-same-origin`, and is fed by `srcdoc`, not `src`;
- the reference calculator's controls (plan toggle, sliders, checkboxes, reset) operate inside the frame;
- oversized and corrupt payloads fall back to the shared unviewable state with download preserved.

## 12. Delivery order

1. Add the `.html` adapter, `check_html`, and focused verification tests.
2. Split `frontend-design/DESIGN.md` from HTML's web-runtime rules and compose the shared guidance into every installed format skill at image build.
3. Add the sandbox HTML skill, extend `load_artifact_instructions`, insert the interactive-intent routing branch ahead of the PDF default, and update the roster and routing tests.
4. Add `HtmlFileViewer`, register `text/html`, and add format metadata.
5. Add the attachment/`nosniff` serving regression test and the sandbox-to-save integration test.
6. Run cross-format regression and update `artifacts-overhaul.md` §7–§9.

Each step leaves one format-neutral path. If any step needs a format-specific persistence or route branch, stop and repair the shared boundary instead.

## 13. Exit criteria

1. Interactive requests route to HTML on intent alone — no format word required — ahead of the PDF default, and produce a self-contained fragment; static requests and explicit formats are unaffected.
2. The fragment verifies programmatically with no preview or visual review.
3. Save and revision use the same document-backed artifact model as PDF, DOCX, PPTX, and XLSX.
4. The authenticated artifact panel renders the page in a sandboxed iframe with no same-origin power, and the header still downloads the original `.html`.
5. `text/html` is attachment-only with `nosniff` on every backend route, and no artifact HTML executes on the SurfSense origin.
6. No HTML-specific schema, persistence API, search path, or document-editor path exists.
7. PDF, DOCX, PPTX, XLSX, Markdown, and unknown-format behavior remain green.
