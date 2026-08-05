# Artifacts Overhaul — Engineering Spec

**Status:** Draft for review
**Scope:** All non-media generated deliverables (PDF, DOCX, PPTX, XLSX, Markdown, and future formats). Media artifacts (podcast, video, image) are explicitly out of scope — they work today and keep their pipelines.
**Decision summary:** Replace the genre-based deliverable system (`generate_report`, `generate_resume`, Typst) with a format-based system: the agent writes code in a sandbox using per-format skills, persists real files write-through as `Document` + `DocumentFile`, and the frontend renders by MIME type. Typst is removed entirely. Artifacts are **view-only** (Plate survives only for memory/team-memory editing) and **unversioned** — revisions replace the artifact in place; the conversation is the history. No fallbacks, no feature flags, **no data migration** — legacy code and the `reports` table are deleted outright; previously generated deliverables become inaccessible (§10), announced as a breaking change in release notes.

---

## 1. Motivation & principles

### 1.1 Current failure modes

1. **Two parallel stores that don't know about each other.**
   - `generate_report` / `generate_resume` write immediately to the `reports` table (`app/db.py`, `Report` model) — never `Document`, never `DocumentFile`.
   - `write_file` / `edit_file` stage content in agent state and commit at end-of-turn via `KnowledgeBasePersistenceMiddleware.commit_staged_filesystem_state` as `Document` rows with `DocumentType.NOTE`.
   - Users see two different "saved" surfaces (artifacts library vs documents tree) with different behavior.
2. **Silent staged-commit failures.** The KB commit wraps everything in `except: log and return None` (`kb_persistence/middleware.py` ~L1242). The tool already told the model "Updated file …" mid-turn, so when the commit fails the user was promised a save that never happened. This is the "YouTube summary sometimes doesn't save" bug.
3. **Verb-gated deliverables.** The report tool docstring only triggers on creation verbs ("write/create/generate/draft…"). "Summarize this video" often fails the gate and the answer stays in chat — inconsistent by design.
4. **Everything renders as markdown.** There is exactly one artifact rendering path (report panel: Plate/markdown, or Typst→PDF recompile for resumes). Asking for a PPTX produces markdown. Asking for a PDF produces a fixed Typst-templated layout the user cannot influence.
5. **Fragile resume pipeline.** Resumes store *Typst source*, not the compiled PDF. Every preview recompiles; a package or environment change after generation breaks a previously "successful" resume.

### 1.2 Design principles

1. **Genre is the model's job. Format is the skill's job. Rendering is the extension's job.**
   There are no genre-specific tools. "Resume", "report", "memo", "invoice" are user intents the model maps to a file format. Evidence: Claude's file-creation feature has no resume tool — the model reasons "a resume is a formal document → .docx/.pdf", loads the format skill, generates, and verifies (Anthropic Agent Skills docs; anthropics/skills repo).
2. **Artifacts are real files with immutable bytes.** What was generated is what renders and what downloads. No recompile-on-view.
3. **Write-through persistence.** The artifact is persisted inside the tool call that produced it, and the tool result carries the `document_id`. Failure is visible to the model in the same turn. No end-of-turn staging for artifacts.
4. **Format knowledge lives in exactly two places:** skills (generation side) and the viewer registry (rendering side). The tool contract, persistence, storage, serving, and deletion layers never enumerate formats. Unknown formats degrade to a download card, never an error.
5. **One store.** Every generated artifact is a `Document` + `DocumentFile` pair. The `reports` table is dropped **without data migration** — legacy deliverables are not carried forward (§10).
6. **No fallbacks.** One sandbox provider per deployment mode, selected by env var. Old code paths are deleted, not flagged off.

---

## 2. Current-state map (what exists today)

### 2.1 Path A — reports/resumes (immediate, `reports` table)

```
task(deliverables) → generate_report | generate_resume
  → LLM produces markdown (report) or Typst body (resume; compiled for page-count validation only, PDF discarded)
  → INSERT Report (content, content_type='markdown'|'typst', report_style, thread_id, workspace_id)
  → with_receipt(...) → ToolMessage JSON
  → frontend: collect-artifacts.ts → artifact card → report-panel.tsx
      content_type 'typst'   → PdfViewer on /api/v1/reports/{id}/preview  (recompiles every view)
      content_type 'markdown'→ Plate editor / MarkdownViewer
  → export: /api/v1/reports/{id}/export (pandoc → report_pdf.typst → typst.compile)
```

Versioning today: each regeneration inserts a **new sibling `Report` row** sharing `report_group_id`; `_get_version_siblings()` in `reports_routes.py` powers the version-switcher dropdown in `report-panel.tsx`. This entire mechanism dies with the table — the new system is deliberately unversioned (§4.3), and nothing replaces the switcher.

Key files:

- Tools: `surfsense_backend/app/agents/chat/multi_agent_chat/subagents/builtins/deliverables/tools/{report.py,resume.py,index.py}`
- Model: `Report` in `surfsense_backend/app/db.py`
- Routes: `surfsense_backend/app/routes/reports_routes.py`, Typst branches in `editor_routes.py`, `public_chat_routes.py`
- Templates: `surfsense_backend/app/templates/report_pdf.typst`, `export_helpers.py`
- Frontend: `surfsense_web/features/chat-artifacts/**`, `features/artifacts-library/**`, `components/report-panel/{report-panel,pdf-viewer}.tsx`, `components/tool-ui/generate-{report,resume}.tsx`, `atoms/chat/report-panel.atom.ts`, `lib/apis/reports-api.service.ts`
- Streaming: `surfsense_backend/app/tasks/chat/streaming/handlers/tools/deliverables/generate_{report,resume}/`
- Deps: `typst>=0.14.0`, rendercv (Typst package, referenced inline in `resume.py`), `pypandoc`

### 2.2 Path B — KB notes (staged, `documents` table)

```
write_file | edit_file under /documents/…
  → staged in agent state (dirty_paths)
  → end of turn: KnowledgeBasePersistenceMiddleware.aafter_agent → commit_staged_filesystem_state
  → Document(document_type=NOTE) + chunks + embeddings
```

This path is **kept** for incidental notes. It is no longer used for artifacts.

### 2.3 Existing infrastructure the new system reuses

- **File storage** (`surfsense_backend/app/file_storage/`): `store_document_file()` writes bytes via the configured backend and adds a `DocumentFile` row (storage key shape `documents/{workspace_id}/{document_id}/{kind}/{uuid}{ext}`, sha256 checksum, size, MIME). Backends: `LocalFileBackend` (Docker volume, self-hosted) and `AzureBlobBackend` (cloud), selected by `FILE_STORAGE_BACKEND`. `open_document_file_stream()` streams in 1 MB chunks. `purge_document_blobs()` handles deletion.
- **Skills system** (`main_agent/skills/`): existing loader used by the `report-writing` builtin skill. Reused as-is for format skills (progressive disclosure: frontmatter metadata always in prompt; body loaded on trigger).
- **PDF viewer** (`surfsense_web/components/report-panel/pdf-viewer.tsx`): virtualized pdf.js canvas viewer with zoom, DPR handling, authenticated fetch (`getAuthHeaders()`), `toolbarActions` slot. Reused unchanged; only the URL source changes. (`pdfjs-dist` already a dependency.)
- **Document viewer plumbing**: `GET .../documents/{id}/editor-content` (`editor_routes.py`) already decides `viewer_mode` per document; extended in this spec with a file shape.
- **Sandbox seam** (`shared/middleware/filesystem/sandbox.py` + `tools/execute_code/` + `routes/sandbox_routes.py`): a working Daytona integration already exists — per-thread sandbox cache with locks and broken-state recovery, KB file sync into the sandbox, heredoc-based `execute_code` (no persistent kernel), and a local-disk file download path (`SANDBOX_FILES_DIR`). Phase 2 refactors this seam behind the provider protocol (registry logic promoted, Daytona specifics extracted, OpenSandbox added); the local-disk download path is obsoleted by `save_artifact` and deleted in phase 4. Details: [`phase-2-sandbox-pdf.md`](./phase-2-sandbox-pdf.md) §2.1.

---

## 3. Frozen contracts

Everything else in this spec can evolve; these two schemas are the interfaces every phase builds on. Changes after phase 1 require a spec revision.

### 3.1 `save_artifact` tool result

```json
{
  "status": "saved",
  "document_id": 123,
  "title": "Indian History — Overview",
  "files": [
    {
      "file_id": 456,
      "role": "primary",
      "filename": "indian-history.docx",
      "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "size_bytes": 48213
    },
    {
      "file_id": 457,
      "role": "preview",
      "filename": "indian-history.pdf",
      "mime_type": "application/pdf",
      "size_bytes": 91240
    }
  ]
}
```

- `files` is empty for markdown artifacts (content lives in `Document.source_markdown`; no blob).
- `role` is `"primary"` (the deliverable) or `"preview"` (browser-renderable derivative, currently always PDF). At most one of each per artifact v1.
- **Revision:** the tool accepts an optional `document_id` input. Present → revise that artifact **in place** (§4.3): same `document_id`, new `DocumentFile` rows replace the old ones transactionally. Absent → create a new artifact. There is no version history (§8.4).
- On failure the tool returns `{"status": "failed", "error": "<human-readable reason>"}` — the model sees it in-turn and can retry or tell the user. No silent paths. A failed revision leaves the existing artifact untouched.
- The chat artifact card is built from this payload (`document_id` replaces `report_id` as `entityId` in `features/chat-artifacts/model/artifact.ts`).

### 3.2 `editor-content` response (extended)

The existing endpoint gains a discriminated union on `kind`:

```json
// Text shape — markdown artifacts, notes, all existing documents (unchanged fields)
{
  "kind": "text",
  "document_id": 123,
  "title": "…",
  "source_markdown": "…",
  "generated": false,
  "viewer_mode": "plate" | "monaco",
  "...": "existing fields unchanged"
}

// File shape — documents whose primary content is a stored binary
{
  "kind": "file",
  "document_id": 123,
  "title": "Indian History — Overview",
  "generated": true,
  "files": [
    { "file_id": 456, "role": "primary", "filename": "indian-history.docx",
      "mime_type": "application/vnd...", "size_bytes": 48213,
      "content_url": "/api/v1/workspaces/7/documents/123/files/456/content" },
    { "file_id": 457, "role": "preview", "filename": "indian-history.pdf",
      "mime_type": "application/pdf", "size_bytes": 91240,
      "content_url": "/api/v1/workspaces/7/documents/123/files/457/content" }
  ],
  "updated_at": "…"
}
```

- Backend decides `kind`: a document with a `GENERATED` `DocumentFile` whose primary is non-markdown → `file`; otherwise `text`. The client never guesses.
- **`generated` is present in both shapes.** `generated: true` → the client renders read-only, unconditionally; `viewer_mode` is ignored for generated documents (it remains meaningful only for regular KB documents, where Plate survives solely for memory/team-memory editing — see §8.4).

---

## 4. Storage design

### 4.1 Data model

**No new tables.** Two additive schema changes (one Alembic migration):

1. `DocumentFileKind.GENERATED` added to the `document_file_kind` enum (`app/file_storage/persistence/enums.py`). Existing kinds (`ORIGINAL`, `REDACTED`, `FILLED_FORM`) untouched.
2. `document_files.role` column: `VARCHAR(16) NOT NULL DEFAULT 'primary'` — values `primary` | `preview`. Existing rows default to `primary` (correct for uploads).

An artifact is:

- **`Document` row** — title; `source_markdown` = the markdown *representation* of the artifact (full content for markdown artifacts; outline/summary for binary ones — this is what gets chunked and embedded so a PPTX is findable in KB search); `document_metadata` carries `{"generated": true, "thread_id": …, "tool_call_id": …}`. `document_type` stays `NOTE` (provenance is fully determined by the `GENERATED` file kind + metadata flag; a new DocumentType is not needed and would ripple through connector-oriented code).
- **0–2 `DocumentFile` rows** — `kind=GENERATED`; primary (the deliverable) and optionally preview (verification PDF). Created via the existing `store_document_file()`; sha256, size, MIME recorded as today.

Artifacts are deliberately **single-generation**: a Document holds at most one primary + one preview at any time. This differs from uploaded documents, where multiple kinds (`ORIGINAL`, `REDACTED`, `FILLED_FORM`) coexist as siblings — do not unify the two models; uploads keep multi-kind, artifacts are replace-on-revise (§4.3).

**Adjacent tables — explicit fates:**

| Table | Fate | Why |
|---|---|---|
| `reports` | **Dropped in phase 4, no data copy** — including every `report_group_id` sibling version | Legacy deliverable store; the no-migration decision (§10) makes its entire history unrecoverable, deliberately |
| `document_versions` | **Untouched** | Backs KB-document version snapshots written by connector indexers (Obsidian, local-folder sync via `create_version_snapshot`) and the restore endpoints/`version-history.tsx` UI — a content-protection feature unrelated to deliverables. **Fence:** the `save_artifact` revise path must never call `create_version_snapshot`, or versioning sneaks back into artifacts |
| `document_revisions` / `folder_revisions` | **Untouched** | Back the agent-revert feature for KB edits (`revert_service.py`). **Fence:** `save_artifact` creates/revisions are excluded from agent-revert snapshotting — "revert my artifact" would be version history through the back door |

### 4.2 Physical storage

Unchanged from the existing file-storage layer — this is the point:

| Deployment | `FILE_STORAGE_BACKEND` | Bytes live in |
|---|---|---|
| Self-hosted (docker-compose) | `local` | Files on the storage-root Docker volume: `{root}/documents/{ws}/{doc}/generated/{uuid4}.docx` |
| Production | `azure` | Azure Blob, same key |

Postgres never stores bytes. The `DocumentFile.storage_backend` column records which backend wrote the blob, so reads are correct even across a backend migration.

### 4.3 Limits and lifecycle

- **Size cap:** `ARTIFACT_MAX_FILE_BYTES` (default 30 MB, matching Claude's documented cap) enforced when pulling bytes out of the sandbox. Config value, not per-format.
- **File immutability, no version history.** A `DocumentFile`'s bytes are never overwritten — that keeps the sha256 ETag + `immutable` caching correct (§5) and guarantees what was generated is what renders. But there is **no version history**: a revision updates the *same* `Document` in place (same `document_id`; title and `source_markdown` update and re-index) and writes **new** `DocumentFile` rows (new `file_id`s, new storage keys); the old rows and blobs are purged in the same transaction **after** the new generation commits. Consequences, all intended:
  - Every reference (chat cards, library, tree, search, links) is a `document_id` and always resolves to the latest generation — an update propagates everywhere with zero code, exactly Claude's behavior.
  - Cache correctness is free: revised artifacts have new per-`file_id` URLs; old URLs 404 and the panel refetches.
  - A failed revision leaves the previous generation intact — the failure mode is "update didn't happen," never "artifact destroyed."
  - Revisions are **destructive by design**. The prior generation is not recoverable from the system; the conversation is the version history (regeneration from chat context is the way back), and download is the user's escape hatch for keeping a specific generation. Whether and when to download before revising is the **user's decision** — the product adds no nudges, prompts, or retention mechanisms around it.
  - **No back doors:** the revise path never writes `document_versions` (no `create_version_snapshot` call) and is excluded from agent-revert snapshotting (`document_revisions`) — see the table fences in §4.1.
- **Deletion:** existing `purge_document_blobs()` + FK cascade covers it. No new code.

---

## 5. Serving design

One new endpoint; everything renders and downloads through it.

```
GET /api/v1/workspaces/{ws_id}/documents/{doc_id}/files/{file_id}/content
```

1. **Auth:** the same workspace-membership dependency as every other document route. Files are always proxied through the backend — no SAS/presigned URLs in v1, so auth is uniform across local and Azure. <!-- ponytail: proxying costs API-server bandwidth; ceiling is large-file throughput at scale, upgrade path is a 302 to a time-limited SAS URL behind this same route -->
2. **Resolve:** `DocumentFile` row must belong to `doc_id`/`ws_id`; 404 otherwise.
3. **Stream:** `StreamingResponse` over `open_document_file_stream()` with headers:
   - `Content-Type: {row.mime_type}`
   - `Content-Disposition`: `inline` only for MIME types on the inline allowlist (`application/pdf`, `image/*`, `text/plain`); `attachment` for everything else. Always includes the original filename. This is the stored-XSS guard: an agent-generated `.html`/`.svg` downloads instead of executing on our origin.
   - `X-Content-Type-Options: nosniff`
   - `ETag: "{row.checksum_sha256}"`, `Cache-Control: private, max-age=31536000, immutable` — files never change (§4.3), the checksum already exists, so previews are cached client-side forever. Honor `If-None-Match` → 304.

The frontend's existing authenticated-fetch pattern (`getAuthHeaders()` in `pdf-viewer.tsx`) works against this endpoint unchanged.

---

## 6. Agent & tools design

### 6.1 The deliverables subagent keeps its seat; its tools are replaced

Supervisor routing (`task(deliverables, …)`) is unchanged. Inside the subagent, `generate_report` and `generate_resume` are **removed** and replaced with three format-blind tools:

| Tool | Signature (conceptual) | Behavior |
|---|---|---|
| `execute` | `(code_or_command) → stdout/stderr/exit` | Runs in the thread's sandbox session via the provider's persistent kernel (Python) or shell (Node scripts, `soffice`, `pdftoppm`, `pandoc`). |
| `read_sandbox_file` | `(path) → bytes/base64` | Pulls a file back for the model to inspect — primarily the rasterized page JPEGs from the verification loop. Size-capped. |
| `save_artifact` | `(path, title, markdown_representation, preview_path?) → §3.1 payload` | Write-through persist: reads bytes from the sandbox, creates `Document` + `DocumentFile`(s) in one transaction, indexes (chunks + embeddings from `markdown_representation`), returns the contract payload. Markdown artifacts pass content directly with no `path`. |

Streaming emission: one generic `save_artifact` handler replaces the per-tool `generate_report/` and `generate_resume/` emission handlers.

### 6.2 Skill selection (no new machinery)

The existing skills system provides progressive disclosure exactly as Anthropic's spec describes:

- **Level 1** — each format skill's frontmatter (`name`, `description`) is always present in the subagent prompt (~100 tokens/skill). The description states what the skill does *and when to use it* ("Use whenever the user wants a Word document, .docx, report/memo/letter as Word…").
- **Level 2** — the model reads the full `SKILL.md` only when it decides the format is needed (the "Loaded docx skill" step visible in Claude traces).
- **Level 3** — helper scripts (`soffice.py` wrapper, validators, thumbnailers) live in the sandbox image at `/opt/skills/{format}/scripts/` and are executed via `execute`; their source never enters context.

Genre → format mapping is prompt guidance in the subagent system prompt, not code: *"Decide the output format from the user's intent. Resumes/formal documents → docx or pdf. Slides → pptx. Tabular/analytical → xlsx. Ambiguous → pdf, or ask."* The user can always override.

### 6.3 The mandatory verification loop

Every format skill ends with the same discipline (evidence: Anthropic's docx skill "Verify the output" section — this loop is why their documents come out well-formatted):

```
1. Generate the file (docx npm / openpyxl / python-pptx / reportlab-weasyprint).
2. Convert to PDF if not already PDF: soffice --headless --convert-to pdf out.docx
3. Rasterize: pdftoppm -jpeg -r 100 out.pdf page
4. read_sandbox_file the page images; LOOK at them. Check layout, alignment, overflow, blank pages.
5. Broken? Fix the script, regenerate, re-verify.
6. Only then: save_artifact(path=out.docx, preview_path=out.pdf, …)
```

The verification PDF is the preview file — the office-format preview costs zero extra compute because the quality gate already produced it.

### 6.4 Turn flow, end to end (example: "create me a resume")

```
1. Supervisor → task(deliverables, "create a resume with …").
2. Model reasons: resume → formal document → docx (skill descriptions in prompt).
3. Reads docx SKILL.md (Level 2) via sandbox filesystem.
4. execute: node resume.js  → resume.docx        (docx npm preinstalled)
5. execute: soffice → resume.pdf; pdftoppm → page-1.jpg
6. read_sandbox_file(page-1.jpg) → model inspects, fixes issues, regenerates.
7. save_artifact(path=resume.docx, preview_path=resume.pdf, title="…", markdown_representation="…")
   → Document + 2 DocumentFiles persisted; payload returned.
8. Tool result streams; artifact card renders with document_id; right panel auto-opens; PdfViewer streams the preview; Download serves the .docx.
```

Failure at any step is a visible tool error in the same turn — the model retries or reports. There is no path where the user is told "saved" and nothing was saved.

---

## 7. Skills & sandbox design

### 7.1 Launch skills

Four skills, each a directory under the existing skills root (`{format}/SKILL.md` + `scripts/`), authored fresh (Anthropic's skill *files* are license-restricted — "Proprietary, see LICENSE.txt" — so we write our own against the same toolchain, which their docs openly describe):

| Skill | Create with | Verify with | Notes |
|---|---|---|---|
| `pdf` | reportlab / weasyprint (Python) | pdftoppm → inspect | Resumes, reports, letters, one-pagers land here or docx |
| `docx` | `docx` (npm, Node) | soffice → pdf → pdftoppm | Encode the known footguns: DXA table widths, `ShadingType.CLEAR`, numbering for bullets, TOC outline levels, tab stops over PositionalTab |
| `pptx` | python-pptx | soffice → pdf → pdftoppm | Per-slide thumbnails |
| `xlsx` | openpyxl | recalc + read back values | No visual loop; verify formulas/values programmatically |

Adding a format later = one new skill directory + sandbox image rebuild + (optionally) one viewer-registry entry. No backend changes.

### 7.2 Sandbox image (`surfsense/sandbox`)

Single polyglot image, everything preinstalled (the sandbox has **no network egress** at runtime, so skills must never need `pip install`/`npm install`):

- Python 3.12 + `openpyxl`, `python-pptx`, `reportlab`, `weasyprint`, `pypdf`, `pandas`, `matplotlib`
- Node LTS + `docx` (npm, globally installed)
- LibreOffice (`soffice`), Poppler (`pdftoppm`), `pandoc`
- Fonts: DejaVu, Liberation, Noto (incl. CJK) — LibreOffice output quality is font-bound
- Skills at `/opt/skills/`

### 7.3 Provider protocol

```python
class SandboxProvider(Protocol):
    async def get_or_create_session(self, thread_id: str) -> SandboxSession: ...

class SandboxSession(Protocol):
    async def execute(self, code: str, language: str = "python") -> ExecResult: ...
    async def run_command(self, command: str) -> ExecResult: ...
    async def read_file(self, path: str) -> bytes: ...
    async def write_file(self, path: str, data: bytes) -> None: ...
    async def terminate(self) -> None: ...
```

- **Self-hosted:** OpenSandbox — `opensandbox-server` added to `docker-compose.yml`, sandboxes created from `surfsense/sandbox`, persistent-kernel code-interpreter API for warm Python execs (benchmarked rationale: container start 0.3–0.6 s and warm exec ~0.09 s are cheap; the ~450 ms/exec Python import tax is what the persistent kernel eliminates).
- **Cloud:** Daytona, same protocol.
- Selection: `SANDBOX_PROVIDER=opensandbox|daytona` at startup. **A deployment choice, not a fallback chain.**
- Lifecycle: one session per chat thread, created lazily on first `execute`, TTL-reaped (default 15 min idle), hard-killed at thread deletion. Per-workspace concurrent-session limit (default 2) to bound resource use.
- **Gate:** the one-day OpenSandbox spike (compose service up → custom image → persistent-kernel exec → binary file out → kill, measuring warm-exec latency and file egress) must pass before phase 2 implementation starts. If it fails, the fallback *decision* (not runtime fallback) is llm-sandbox's `InteractiveSandboxSession`, accepting that we then own socket security and lifecycle.

---

## 8. Rendering design

### 8.1 One right panel, one registry

The report panel is replaced by a single **artifact panel** that receives a `document_id`, calls `editor-content`, and branches on the §3.2 contract:

- `kind: "text"` → read-only markdown viewer (existing `MarkdownViewer`; **not** Plate).
- `kind: "file"` → the viewer registry picks a component from the **primary** file's MIME type.

### 8.2 Viewer registry (the only format-aware frontend code)

```tsx
const VIEWERS: Record<string, ViewerEntry> = {
  "application/pdf":  PdfFileViewer,      // streams the primary file
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document":   PdfPreviewViewer,
  "application/vnd.openxmlformats-officedocument.presentationml.presentation": PdfPreviewViewer,
  // xlsx intentionally absent → falls through to FileDownloadCard
};
// unmatched MIME → <FileDownloadCard />   (never an error)
```

- `PdfFileViewer` / `PdfPreviewViewer` are thin wrappers around the existing `pdf-viewer.tsx`, pointed at `content_url` of the primary or preview file respectively; the preview variant adds a "Download {filename}" toolbar action (the `toolbarActions` prop exists) hitting the primary file's URL.
- All viewers lazy-loaded via `next/dynamic` (pdf.js stays out of the main bundle).
- Rationale for the matrix: browsers render PDF natively (pdf.js); client-side office renderers were evaluated and rejected on evidence (mammoth discards layout by design; docx-preview approximates; no credible OSS PPTX renderer; MS Office Online viewer requires public URLs). XLSX preview-as-PDF misrepresents spreadsheets (truncated sheets, invisible formulas) → download card, matching Claude's own choice. A values-only SheetJS grid is a possible later registry entry.

### 8.3 Per-format matrix

| Format | Panel shows | Download serves | New code |
|---|---|---|---|
| PDF | The file itself in pdf.js viewer | The PDF | URL change only |
| Markdown | Read-only rendered markdown | `.md` blob | Panel branch |
| DOCX / PPTX | Preview PDF in pdf.js viewer | The real .docx/.pptx | `PdfPreviewViewer` wrapper |
| XLSX / unknown / oversized | File card (name, size, icon) | The file | `FileDownloadCard` |

### 8.4 Editing policy

Generated artifacts are **read-only + regenerate in place**. Revision requests go back through the agent (new sandbox run → same `document_id`, files replaced transactionally, §4.3). Revisions are destructive by design — all chat references converge on the latest generation and prior generations are gone; this is a deliberate product decision mirroring Claude's artifact behavior, not an oversight.

**Product-level boundary:** Plate is retired everywhere except **memory and team-memory** editing. The artifact panel is strictly a renderer — it has no editing surface for any format, *including markdown artifacts*, and no Plate-parity work is ever in scope for artifacts. (The wider Plate retirement outside artifact surfaces is a separate effort; this spec only guarantees artifacts never depend on Plate.)

### 8.5 Chat surfaces

- `ARTIFACT_TOOL_KINDS` / `collect-artifacts.ts`: `save_artifact` maps to one artifact kind (`file`), with icon and label derived from the payload's primary MIME/filename. `report` and `resume` kinds are removed.
- The inline card shows filename, format badge, size, download button; click opens the panel. Desktop auto-open on completion is preserved.

---

## 9. Deprecation & removal (delete, don't flag)

Executed in phase 4, after the legacy card + release-notes warning land (§10). Nothing here is kept behind a flag.

### 9.1 Backend

| Delete | Location |
|---|---|
| `generate_report`, `generate_resume` tools + registration | `subagents/builtins/deliverables/tools/{report.py,resume.py}`, `index.py`, `shared/tools/catalog.py`, prune/tool-name lists |
| `report-writing` builtin skill (rigid template) | `main_agent/skills/builtin/report-writing/` |
| Streaming handlers | `tasks/chat/streaming/handlers/tools/deliverables/generate_{report,resume}/` + dead `save_document/` registry name |
| Reports routes (content, preview, export, public preview) | `routes/reports_routes.py`, Typst branches in `public_chat_routes.py` |
| Typst export path for documents | pandoc→typst branch in `editor_routes.py` (PDF export of markdown documents re-routes through weasyprint; other pandoc formats kept) |
| Templates | `app/templates/report_pdf.typst`, `get_typst_template_path()` in `export_helpers.py` |
| `Report` model + `reports` table (incl. `report_group_id` sibling versions, `_get_version_siblings`) | `db.py` + drop migration — dropped cold, no data copy (§10) |
| Schemas | `schemas/reports.py` |
| Dependencies | `typst`, rendercv assumption; `pypdf` only if no remaining user |
| Tests | `tests/unit/agents/new_chat/tools/test_resume_page_limits.py` |

### 9.2 Frontend

| Delete | Location |
|---|---|
| Report panel + atom (incl. the version-switcher UI — nothing replaces it) | `components/report-panel/report-panel.tsx`, `atoms/chat/report-panel.atom.ts` (pdf-viewer.tsx is **kept** and relocated to a shared path) |
| Tool UIs | `components/tool-ui/generate-{report,resume}.tsx` |
| Artifact kinds `report`/`resume`, typst contentType | `features/chat-artifacts/model/artifact.ts`, `collect-artifacts.ts` |
| Reports API client + types | `lib/apis/reports-api.service.ts`, `contracts/types/reports.types.ts` |
| Typst/`pdfOnly` export special cases | `components/shared/ExportMenuItems.tsx` |
| Artifacts library data source | re-pointed to documents query (§10.3), reports fetch removed |

---

## 10. Legacy deliverables (previously generated files)

**There is no data migration.** The only two coherent options were (a) backfill `reports` rows into Documents, or (b) drop the table and stop showing old deliverables — anything in between means keeping `reports_routes.py` + the report panel alive indefinitely, which defeats the retirement. Option (b) is the decision: phase 4 drops `reports` cold, and previously generated reports/resumes (including all `report_group_id` sibling versions) become **permanently inaccessible**. This is a chosen product trade, consistent with the unversioned-artifacts philosophy (§4.3), not an accident.

What replaces the backfill — two purely presentational things:

### 10.1 Legacy card in old threads

Old chat threads contain `generate_report`/`generate_resume` tool-call parts that something must render forever. They render a **static legacy card**: title from the tool payload, plus "Generated with the previous artifact system — no longer available. Ask me to regenerate it." No lookup, no data fetch, no click-through to a panel. This is the minimal something.

### 10.2 Release-notes breaking-change warning

The release that drops `reports` carries a prominent breaking-change note so self-hosted users can export any deliverables they care about **before** upgrading (the export endpoints exist right up until that version). Documentation, not code — the export decision stays with the user, per the product boundary in §4.3.

### 10.3 Surfaces

- Artifacts library queries Documents (`document_metadata.generated == true` / `GENERATED` file kind) instead of `reportsApiService.list`. Old deliverables simply stop appearing in it on upgrade.
- No `migrated_from_report_id`, no verification gate, no lazy re-indexing, no Typst compile at upgrade time — the `typst` dependency is removed with zero final use.

---

## 11. Delivery phases

Each phase ships independently and leaves the product working. Detailed task breakdowns, file-level plans, and exit criteria live in per-phase spec files; **this document owns the contracts (§3) and the architecture — phase files own execution detail and are revised independently.** A phase file may not contradict §3 without a revision here first.

| Phase | Spec file | One-line scope | Exit gate |
|---|---|---|---|
| 1 — Foundation | [`phase-1-foundation.md`](./phase-1-foundation.md) | Schema, `save_artifact` (markdown path), streaming endpoint, `editor-content` discrimination, artifact panel + registry | Markdown artifacts persist write-through and render; seeded binary file streams + downloads correctly |
| 2 — Sandbox + PDF | [`phase-2-sandbox-pdf.md`](./phase-2-sandbox-pdf.md) | OpenSandbox spike (gate), provider protocol, sandbox image + compose service, `execute`/`read_sandbox_file`, `pdf` skill, `PdfFileViewer` | "Create me a resume as a PDF" flows through the new pipeline with a verified PDF; zero Typst involvement |
| 3 — Office skills | [`phase-3-office-skills.md`](./phase-3-office-skills.md) | docx/pptx/xlsx skills, preview-PDF pairing, `PdfPreviewViewer`, download-card polish, legacy tools demoted to "never use" | All four formats per the §8.3 matrix; unknown formats degrade to the card with no code changes |
| 4 — Demolition | [`phase-4-migration-demolition.md`](./phase-4-migration-demolition.md) | Legacy card + release-notes warning (§10), surface re-pointing, then the full §9 deletion inventory incl. Typst and the `reports` drop | Zero references to `Report`/`typst`/legacy tools; old threads render legacy cards with no data fetch |

Ordering constraints: 1 → 2 → 3 → 4 strictly; the OpenSandbox spike (phase 2, task 0) blocks all phase-2 integration work; the legacy card + release-notes warning (phase 4, §1) land before any deletion PR.

---

## 12. Risks & open questions

| Risk | Mitigation |
|---|---|
| OpenSandbox spike fails (pre-1.0 project) | Decision-level fallback documented (§7.3): llm-sandbox `InteractiveSandboxSession`; protocol isolates the blast radius to one provider file |
| LibreOffice conversion fidelity (fonts, complex layouts) | Fonts baked into image; verification loop catches visual breakage before save — the model sees what LibreOffice renders, not what Word would |
| Sandbox resource exhaustion (self-hosted, small VPS) | Per-workspace session cap, TTL reaper, 30 MB file cap; compose memory limit on the sandbox service |
| Skill licensing | Anthropic skill files are proprietary; ours are authored fresh against the publicly documented toolchain |
| Verification loop cost (multi-modal page inspection per artifact) | ~2–4 extra model calls per artifact; acceptable for deliverable quality. Skills instruct single-image batching (grid of page thumbnails) where page count is high |
| Users lose old deliverables on upgrade (no-migration decision, §10) | Deliberate product trade; release-notes breaking-change warning + pre-upgrade export window are the mitigation — no code |

**Open questions (decide during phase 1 review):**

1. Public/shared-chat rendering of artifacts (public token → file streaming) — in scope for phase 1 contract but implementation may slip to phase 3.
2. Whether `read_sandbox_file` image inspection uses the chat model (needs vision) or a cheaper dedicated vision call — cost/quality tradeoff, provider-configurable.

*(Resolved: retention/GC for superseded versions — moot; revisions replace files in place with no history, §4.3.)*
