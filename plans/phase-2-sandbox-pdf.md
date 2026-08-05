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
| `write_file` | `sandbox.files.write_files([WriteEntry(path, data, mode)])` |
| `read_file` | `sandbox.files.read_file(path)` |
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
- `read_sandbox_file(path)` → bytes (base64 for images so the model can *look* at rendered pages); enforce `ARTIFACT_MAX_FILE_BYTES`.
- Extend `save_artifact` tool with the binary signature: `(path, title, markdown_representation, preview_path?, document_id?)` — reads file(s) from the session, MIME-sniffs (extension first, `python-magic` as check), calls the phase-1 helper with `role=primary` (+ `preview`); `document_id` present → in-place revision (master spec §4.3). Same §3.1 payload.
- Register all in `tools/index.py` / catalog; emission handler from phase 1 covers the payload unchanged.

### 2.4 Skill — `pdf`

`{skills_root}/pdf/SKILL.md` (+ `scripts/`), authored fresh:

- Frontmatter description covering triggers: PDF, resume, CV, report-as-PDF, letter, one-pager, printable.
- Body: reportlab vs weasyprint guidance (weasyprint for HTML/CSS-styled documents, reportlab for programmatic layout), fonts available in the image, page-size defaults.
- **Mandatory verification loop** (master spec §6.3): `pdftoppm -jpeg -r 100 out.pdf page` → `read_sandbox_file` the pages → inspect → fix → only then `save_artifact`.
- Subagent system prompt gains format-selection guidance (master spec §6.2) and demotes `generate_report`/`generate_resume` to "only when the user explicitly declines a file".

### 2.5 Frontend

- `PdfFileViewer` registry entry: existing `pdf-viewer.tsx` (move to `components/shared/pdf-viewer.tsx`; report panel imports from the new path) pointed at the primary file's `content_url`, lazy-loaded.
- Artifact card format badge for `application/pdf`.

### 2.6 Checks

- Provider contract test (runs against OpenSandbox in CI, Daytona smoke in cloud env): create → exec → read → terminate; TTL reap; concurrency cap.
- Integration: "create a one-page PDF listing 3 facts about X" end-to-end → verified PDF renders in panel, ETag-cached on second open, downloads with correct filename.
- Regression: legacy `generate_report` path still functional (it isn't removed until phase 4).

---

## 3. Exit criteria

1. Spike numbers recorded in this file (create/warm-exec/read latencies) — §7.3 of the master spec becomes "verified in SurfSense".
2. "Create me a resume as a PDF" → model picks pdf skill → generates → visually verifies (page images demonstrably read by the model in the trace) → `save_artifact` → renders in panel, downloadable, KB-searchable. Zero Typst involvement.
3. Sandbox lifecycle: session reused within a thread (warm exec < 150 ms), reaped after idle TTL, capped per workspace with a clean error.
4. Self-hosted compose up works on a machine with no KVM and no cloud credentials.
