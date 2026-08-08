# Phase 2 — Sandbox + PDF skill

**Parent spec:** [`artifacts-overhaul.md`](./artifacts-overhaul.md) (§6 tools, §7 sandbox/skills, §3 contracts).
**Depends on:** phase 1 complete (persistence helper, streaming endpoint, panel/registry all live).
**Goal:** code execution in a sandboxed environment and the first real file format. After this phase, resumes and PDF reports flow through the new pipeline.
**Ships to users:** "create me a PDF/resume" produces an agent-designed, visually verified PDF rendering inline in the artifact panel.

---

## 0. Gate: OpenSandbox spike (day 1, blocks everything else)

Stand up and measure before writing integration code:

1. `opensandbox-server` service in a local `docker-compose` override.
2. Build draft `surfsense/sandbox` image (§2.2 below, minimal: Python + Node + LibreOffice + Poppler).
3. Via the OpenSandbox Python SDK (`opensandbox` + `opensandbox-code-interpreter`): create sandbox from the image → exec via persistent kernel → write a PDF with reportlab → read the bytes back → terminate.
4. Measure: sandbox create time, warm exec latency (target < 150 ms after first exec), file read throughput.
5. Verify two API behaviors (both evidenced by the OpenSandbox MCP tool surface — `sandbox_list` with `filter`, `sandbox_connect`, `sandbox_renew` — which wraps the same SDK; confirm the SDK-level equivalents work as expected):
   - **Session rediscovery:** list/filter by our `metadata={"surfsense_thread": id}` + connect by ID after a backend restart (Daytona `find_one(labels=…)` equivalent).
   - **Timeout extension:** renew expiration on activity (Daytona auto-stop-reset equivalent). If either behaves unexpectedly, the registry falls back to persisting `thread_id → sandbox_id` and recreating expired sessions transparently.

Note: the OpenSandbox **MCP server** (`opensandbox-mcp`) is *not* part of this integration — its file tools are text-only and it lacks code-interpreter contexts; our backend uses the Python SDK in-process. (`surfsense_mcp` is unrelated: it exposes SurfSense features to external MCP clients.)

**Pass** → proceed. **Fail** → decision-level fallback is llm-sandbox `InteractiveSandboxSession` (master spec §7.3); revise this phase file, not the master contracts — the provider protocol makes the blast radius one implementation file.

### Spike result (verified 2026-08-07)

`surfsense/sandbox:dev` against `opensandbox/server:v0.2.2` passed:

- sandbox create: **4004.72 ms**
- persistent-kernel executions: **4949.77 ms cold**, then **184.15,
  187.91, 83.20, 80.13 ms**; steady median (excluding cold): **133.68 ms**
- 1372-byte PDF `read_bytes`: **33.28 ms**
- metadata-filtered rediscovery + connect: **passed**
- timeout renewal: **passed**

The measured steady median is below the 150 ms gate, so OpenSandbox remains the
selected self-hosted provider.

### Research corrections recorded during implementation

1. **SDK mapping:** binary reads use `sandbox.files.read_bytes(path)`;
   rediscovery uses `SandboxManager.list_sandbox_infos(SandboxFilter(metadata=…))`
   followed by `Sandbox.connect(id)`; renewal is
   `sandbox.renew(timedelta(...))`. `commands.run` returns an execution whose
   stdout and exit code are flattened by the provider.
2. **Vision stays inside a tool:** this stack serializes tool results as text,
   so image bytes cannot travel back as multimodal `role=tool` content.
   `inspect_sandbox_images(paths, instructions)` reads rendered JPEGs, makes one
   workspace vision-model call, and returns a text QA report.
   `read_sandbox_file` is therefore UTF-8 text-only and size-capped.
3. **Image base:** persistent code-interpreter contexts require
   `opensandbox/code-interpreter:v1.1.0` and its
   `/opt/code-interpreter/code-interpreter.sh` entrypoint; an arbitrary image
   supports commands/files but not the warm kernel used here.
4. **Server deployment shape:** current OpenSandbox publishes
   `opensandbox/server:v0.2.2`, so SurfSense pins that image rather than building
   the older `pip install opensandbox-server` wrapper. It still requires the
   TOML config, SQLite volume, and host Docker socket to spawn sibling sandboxes.
5. **Skill delivery:** deliverables subagents do not receive main-agent
   `SkillsMiddleware` metadata. Level 1 is a static PDF skill listing in the
   deliverables prompt; Level 2 reads `/opt/skills/pdf/SKILL.md` with `execute`.
   No additional middleware is introduced. <!-- ponytail: static prompt text;
   ceiling is drift from the image, upgrade path is pack-time generation -->

---

## 1. Scope

In: provider protocol + two implementations, sandbox image + compose service, `execute` + `read_sandbox_file` tools, session lifecycle, `pdf` skill, binary `save_artifact` path in the tool, `PdfFileViewer` registry entry, format-selection prompt guidance.

Out: office skills/viewers (phase 3), any deletion (phase 4). Legacy tools still registered; prompt demotes them for PDF-able requests.

---

## 2. Tasks

### 2.1 Backend — provider protocol + implementations (refactor, not greenfield)

**SurfSense already has the integration seam**: `shared/middleware/filesystem/sandbox.py` is a complete Daytona provider (per-thread cache max 20, per-thread asyncio locks, label-based discovery, broken-state recovery, `sync_files_to_sandbox`, `network_block_all=True`), consumed by the `execute_code` tool (`tools/execute_code/helpers.py`, heredoc `python3 << EOF` — no persistent kernel) and `routes/sandbox_routes.py` (local-disk file downloads via `SANDBOX_FILES_DIR`). This phase refactors along that seam:

- `app/sandbox/protocol.py`: `SandboxProvider` / `SandboxSession` / `ExecResult` exactly as master spec §7.3.
- `app/sandbox/registry.py`: the provider-agnostic session registry — **promote the existing cache/lock/recovery/retry logic out of `sandbox.py`** (it is proven code), add idle-TTL reaper, per-workspace concurrency cap. Cap returns a clear tool error ("sandbox limit reached — retry shortly") rather than queuing. <!-- ponytail: no queueing; ceiling is UX under heavy parallel use, upgrade path is a bounded wait queue in the registry -->
- `app/sandbox/providers/daytona.py`: extract the Daytona specifics from `sandbox.py` (create-from-snapshot, labels, `fs.download_file`, `upload_files`).
- `app/sandbox/providers/opensandbox.py`: new. SDK mapping:

| Protocol | OpenSandbox SDK |
|---|---|
| create session | `Sandbox.create(SANDBOX_IMAGE, connection_config=ConnectionConfig(domain, api_key), timeout=timedelta(seconds=TTL), metadata={"surfsense_thread": id}, network_policy=NetworkPolicy(defaultAction="deny"), resource={...})` |
| `execute(code, "python")` | `CodeInterpreter.create(sandbox)` once per session, then `interpreter.codes.run(code, language=SupportedLanguage.PYTHON)` — default context persists state across runs (the warm-kernel win) |
| `run_command(cmd)` | `sandbox.commands.run(cmd)` |
| `write_file` | `sandbox.files.write_file(path, data)` |
| `read_file` | `sandbox.files.read_bytes(path)` |
| `terminate` | `sandbox.kill()` |

- `app/sandbox/factory.py`: `SANDBOX_PROVIDER=opensandbox|daytona` (+ `OPENSANDBOX_DOMAIN`, `OPENSANDBOX_API_KEY`, `SANDBOX_IMAGE`, `SANDBOX_IDLE_TTL_SECONDS=900`, `SANDBOX_MAX_SESSIONS_PER_WORKSPACE=2`, `ARTIFACT_MAX_FILE_BYTES=31457280` in `app/config`; existing `DAYTONA_*` vars feed the daytona provider unchanged).
- `execute_code` tool migrates to the protocol: `interpreter.codes.run` replaces the heredoc wrapper for Python; the retry-once-on-failure wrapper in `helpers.py` is kept. `sync_files_to_sandbox` is kept, calling protocol `write_file`.
- **Obsoleted by `save_artifact` (deleted in phase 4, not here):** `persist_and_delete_sandbox`, `SANDBOX_FILES_DIR` local persistence, and the `/threads/{id}/sandbox/download` route — artifacts persist to object storage at generation time, so nothing needs rescuing from a dying sandbox.

**Deployment topology (self-hosted):** `opensandbox-server` compose service with `/var/run/docker.sock` mounted (it spawns sandbox containers as *siblings* via the host daemon); the Docker socket exists **only** in that service, never in the backend or sandboxes. The backend's entire coupling is HTTP + API key to `opensandbox-server:8080`.

### 2.2 Sandbox image (`surfsense/sandbox`)

- `docker/sandbox/Dockerfile`: Python 3.12 (`openpyxl`, `python-pptx`, `reportlab`, `weasyprint`, `pypdf`, `pandas`, `matplotlib`), Node LTS + global `docx`, LibreOffice, Poppler (`pdftoppm`), `pandoc`, fonts (DejaVu, Liberation, Noto + CJK), skills at `/opt/skills/`.
- No network egress at runtime (OpenSandbox egress config default-deny). Everything preinstalled; skills must never instruct `pip/npm install`.
- CI job builds and pushes the image; compose references a pinned tag.
- `docker-compose.yml`: add `opensandbox-server` service + volume; document memory limit knob for small hosts.

### 2.3 Backend — agent tools

- `execute(code_or_command, language="python"|"bash")` → session exec; result = stdout/stderr/exit, truncated to a context-safe length with full output kept in the sandbox at a temp path the model can grep.
- `read_sandbox_file(path)` → UTF-8 text, size-capped by `ARTIFACT_MAX_FILE_BYTES`. Rendered JPEG pages use `inspect_sandbox_images(paths, instructions)`, which performs one internal vision call and returns text findings.
- Extend `save_artifact` tool with the binary signature: `(path, title, markdown_representation, preview_path?, document_id?)` — reads file(s) from the session, MIME-sniffs (extension first, `python-magic` as check), calls the phase-1 helper with `role=primary` (+ `preview`); `document_id` present → in-place revision (master spec §4.3). Same §3.1 payload.
- Register all in `tools/index.py` / catalog; emission handler from phase 1 covers the payload unchanged.

### 2.4 Skill — `pdf`

`{skills_root}/pdf/SKILL.md` (+ `scripts/`), authored fresh:

- Frontmatter description covering triggers: PDF, resume, CV, report-as-PDF, letter, one-pager, printable.
- Body: reportlab vs weasyprint guidance (weasyprint for HTML/CSS-styled documents, reportlab for programmatic layout), fonts available in the image, page-size defaults.
- **Mandatory verification loop** — the visual shape of the §2.6 contract: `pdftoppm -jpeg -r 100 out.pdf page`, then `inspect_sandbox_images` (all pages in one call while the document is short; one call per page plus a final whole-document pass once it is long), then fix the source and repeat, then the structural check, and only then `save_artifact`. The rasterizer and the structural check ship as this skill's own `scripts/`.
- Subagent system prompt gains format-selection guidance (master spec §6.2) and demotes `generate_report`/`generate_resume` to "only when the user explicitly declines a file".

### 2.5 Frontend

- `PdfFileViewer` registry entry: existing `pdf-viewer.tsx` (move to `components/shared/pdf-viewer.tsx`; report panel imports from the new path) pointed at the primary file's `content_url`, lazy-loaded.
- Artifact card format badge for `application/pdf`.

### 2.6 Verification-loop architecture

The whole mechanism lives in this phase; later phases add format skills that use
it and nothing else. The test of that boundary: adding a format must need only a
`SKILL.md`, its own `scripts/`, and a viewer registry entry.

**The contract.** Generate → render evidence → inspect → fix → structural check →
only then `save_artifact`; never save before verifying (master spec §6.3). Two
shapes are permitted and a skill states which it uses: *visual* (rasterize to
JPEG, review with `inspect_sandbox_images`) or *programmatic* (read values back
and assert). `pdf` in §2.4 is the reference implementation of the visual shape.

**Granularity** (master spec §6.3, stated here because skills inherit it):
*generation* is incremental only where units are independent — slides and
worksheets yes, a flowing PDF no, since pagination is emergent and nothing is
"page 2" until the whole document renders. *Verification* batches while the
document is short (up to roughly four pages, where the findings that matter are
cross-page reflow ones that per-page inspection cannot see) and goes one page or
slide per call once it is long or is a deck, followed by one consistency pass
over a bounded sample — first, last, and whatever changed. The sample must be
bounded because `_MAX_VISION_IMAGES` is a hard error rather than a truncation:
"inspect everything" is unavailable to a 40-page document, which is precisely
why the long case iterates instead of batching.

**The shared surface is the tool, not the scripts.** `inspect_sandbox_images`
accepts JPEG only, at most `_MAX_VISION_IMAGES` paths, and 5 MB per image,
rejecting anything else with an actionable error — so a skill cannot silently
render something incompatible. Skills therefore stay self-contained: each ships
its own `{skills_root}/<name>/scripts/` as `pdf` does, with no cross-skill paths
and no shared directory competing with real skills under `/opt/skills/`.
Duplicating a 15-line rasterizer is cheaper than an indirection every skill
depends on, and it leaves room for genuine per-format differences (per-slide
naming, a conversion step first). <!-- ponytail: copies over a shared script;
ceiling is a fix landing in N skills, and the tool's input check is what stops a
stale copy from breaking the loop -->

**Step rendering — pending.** The loop is skill text driving `execute` +
`inspect_sandbox_images`, so nothing below changes loop logic. What is missing is
display: the user should watch generate → render → inspect → fix as named steps
instead of opaque tool calls.

- `timeline/tool-registry/registry.ts` binds `execute` to
  `components/tool-ui/sandbox-execute.tsx`, which was written for the legacy
  `execute_code` tool: it reads `args.command` while this phase's tool passes
  `code_or_command`, so the step header renders `…` today. Rewrite against the
  new shapes — plain-string result, no `SANDBOX_FILE:` markers, no
  `/threads/{id}/sandbox/download` (that route is obsoleted per §2.1).
- `inspect_sandbox_images` has no registry entry at all; add one that renders
  the QA report as a single collapsible step.
- Optional one-line `description` arg on both tools, surfaced through
  `timeline/subagent-rename.ts:resolveItemTitle` — which already derives
  per-call titles from args for `task` — so a step reads "Fix vertical alignment
  on slide 4" rather than the tool name. <!-- ponytail: the model authors the
  title, no server-side summarizer; ceiling is a model that omits it, and the
  fallback is the tool name, which is exactly today's behavior -->

### 2.7 Checks

- Provider contract test (runs against OpenSandbox in CI, Daytona smoke in cloud env): create → exec → read → terminate; TTL reap; concurrency cap.
- Integration: "create a one-page PDF listing 3 facts about X" end-to-end → verified PDF renders in panel, ETag-cached on second open, downloads with correct filename. The assertion that the §2.6 loop actually ran (render and inspect steps present in the trace) belongs to this harness, which later format skills parameterize rather than rebuild.
- Regression: legacy `generate_report` path still functional (it isn't removed until phase 4).

---

## 3. Exit criteria

1. Spike numbers recorded in this file (create/warm-exec/read latencies) — §7.3 of the master spec becomes "verified in SurfSense".
2. "Create me a resume as a PDF" → model picks pdf skill → generates → visually verifies (page images demonstrably read by the model in the trace) → `save_artifact` → renders in panel, downloadable, KB-searchable. Zero Typst involvement.
3. Sandbox lifecycle: session reused within a thread (warm exec < 150 ms), reaped after idle TTL, capped per workspace with a clean error.
4. Self-hosted compose up works on a machine with no KVM and no cloud credentials.
