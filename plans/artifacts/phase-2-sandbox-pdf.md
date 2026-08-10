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
- Skills are copied in from `docker/sandbox/skills/`, which is also what the §2.6 roster check reads — one source for the image and the prompt's Level 1 listing.
- CI job builds and pushes the image; compose references a pinned tag.
- `docker-compose.yml`: add `opensandbox-server` service + volume; document memory limit knob for small hosts.

### 2.3 Backend — agent tools

- `execute(code_or_command, language="python"|"bash")` → session exec; result = stdout/stderr/exit, truncated to a context-safe length with full output kept in the sandbox at a temp path the model can grep.
- `read_sandbox_file(path)` → UTF-8 text, size-capped by `ARTIFACT_MAX_FILE_BYTES`. Rendered pages use `inspect_sandbox_images(paths, instructions, mode)`, which performs the vision calls internally and returns text findings.
- `inspect_sandbox_images` takes **every** page, whatever the count, and the `mode` decides how they are looked at. `mode="each"` (default) makes one single-image call per path, **fanned out concurrently** behind a small semaphore, and concatenates the findings — per-page attention at roughly the latency of one call. `mode="together"` compares pages against each other in **consecutive windows** of up to `_MAX_VISION_IMAGES`; a single image has nothing to compare and says so. Both are uniform rules: the caller never does cap arithmetic, never picks a sample, and never branches on page count. JPEG only (`.jpg`/`.jpeg`, the same format under two extensions), 5 MB per image.
- Fan-out changes failure handling. Gather with `return_exceptions=True` and report per-page failures inline: at one call per document an exception losing everything was acceptable, at one per page it would discard the findings that succeeded. The semaphore is not decoration either — providers rate-limit, and the quota wrapper runs a reserve/finalize per `ainvoke`, so unbounded concurrency is contention against a single credit pool.
- Resolve `get_vision_llm()` **once per tool instance**: the tool currently opens a DB session on every invocation (fine at one call per document, silly at one per page).
- Hosted-plan billing multiplies the same way — `get_vision_llm` wraps premium global configs in `QuotaCheckedVisionLLM` and every `ainvoke` is a `billable_call` reserve/finalize plus a `TokenUsage` row, now per page. (BYOK and free configs come back unwrapped, so self-hosting sees none of this.) Pass a `usage_type` of its own instead of inheriting the wrapper's `vision_extraction` default, or artifact verification becomes indistinguishable from indexing OCR in the audit trail at exactly the moment it becomes the larger consumer.
- Extend `save_artifact` tool with the binary signature: `(path, source_path, title, markdown_representation, preview_path?, document_id?)` — reads file(s) from the session, MIME-sniffs (extension first, `python-magic` as check), calls the phase-1 helper with `role=primary` (+ `preview`, + `source`); `document_id` present → in-place revision (master spec §4.3). Same §3.1 payload.
- **`source_path` is required, not optional, for file artifacts**, and `load_artifact_source(document_id)` materializes it back into the session on request. The alternative — letting a revision reuse whatever is still sitting in `/workspace` — looks cheaper and is two code paths: the sandbox is reaped after `SANDBOX_IDLE_TTL_SECONDS`, so the same user request would be an edit before the timer and a rebuild-from-summary after it, with the second silently producing a different document. Reading from storage every time collapses that into one path whose behavior does not depend on the clock. The source is a `DocumentFile` like the others, so it is replaced on revise and purged with the artifact. `editor-content` has to learn to omit it — the route returns every `GENERATED` file today, so without a filter the panel payload would carry a `content_url` for the generating script, which is the agent's input and not a user download. Reading it out of the sandbox goes through the same `_read_artifact_file` as the deliverable, and the existing `text/*`-to-`text/*` compatibility rule already covers `.html` and `.py`; `.js` is the one to pin with a test, since `mimetypes` answers `text/javascript` on 3.12 and `application/javascript` on older interpreters, and only the first is compatible with the `text/plain` that `magic` sniffs. Size needs no thought — tens of kilobytes against a 30 MB cap.
- **The model cannot revise what it cannot name.** The deliverables subagent is invoked fresh per `task(…)` call and keeps no state between turns, so a second-turn "make the header bigger" reaches it with no `document_id` and it creates a sibling document — the failure the revise input exists to prevent, reached by default. A context hint prepended to each run carries the roster: this chat's generated documents, most recent first, with id, title and filename, capped. Resolve the chat from the invocation's runtime config on every call and never from a value captured at build time — compiled graphs are cached across chats, and a captured id eventually offers one conversation another's artifacts. The query filters `document_metadata.generated` and the thread id, which is an expression index rather than a reason to move either field into a column and split the predicate's home away from the fences in master spec §4.1.
- Prompt and docstring carry the three things the roster alone does not say: that the id comes from the roster, that revising starts with `load_artifact_source`, and that creating is the default whenever the user is not clearly pointing at an existing artifact. The last one is the only guard against destroying the wrong deliverable, since a missing id costs a duplicate and a wrong one is unrecoverable.
- **`save_artifact` enforces the verification gate**: reject a primary file whose mtime is newer than the most recent verification in this session, with an error naming the missing step. The check is temporal, not provenance-based — the tool cannot know that `page-1.jpg` came from `out.pdf`, but rendering necessarily happens after generating, so "generated, then verified" and "verified, then regenerated" are distinguishable by ordering alone. A verification is an `inspect_sandbox_images` call or a clean-exit structural/assertion script, so the programmatic shape (§2.6) passes the same gate. A cache hit inside the vision tool still counts: the model asked and received findings, so record verifications independently of how they were answered. <!-- ponytail: mtime ordering, not content provenance; ceiling is a false rejection when regeneration is byte-identical, whose cost is one extra inspection call and whose error message says exactly that -->
- This is what makes the §2.6 loop an invariant instead of a sentence each skill repeats and each model may skip. It is also the reason phase 3's skills are shorter than `pdf`'s.
- **The gate distinguishes "did not verify" from "could not verify."** A model that simply never inspected is refused. A model that tried and hit an impossibility — `get_vision_llm` returned `None` because the workspace has no vision-capable model, or `QuotaCheckedVisionLLM` raised `QuotaInsufficientError` partway through — saves anyway, with the reason recorded in `document_metadata` and stated in the tool result so the turn's summary can be honest about it. Throwing away a finished deliverable because the workspace cannot afford to look at it is the worse failure, and unlike a lazy model the user cannot fix it by trying again. `inspect_sandbox_images` therefore records *why* it failed rather than only raising, since only it can tell an unavailable model apart from a bad call.
- Register all in `tools/index.py` / catalog; emission handler from phase 1 covers the payload unchanged.

### 2.4 Skill — `pdf`

`{skills_root}/pdf/SKILL.md` (+ `scripts/`), authored fresh:

- Frontmatter description covering triggers: PDF, resume, CV, report-as-PDF, letter, one-pager, printable.
- Body: reportlab vs weasyprint guidance (weasyprint for HTML/CSS-styled documents, reportlab for programmatic layout), fonts available in the image, page-size defaults.
- **Mandatory verification loop** — the visual shape of the §2.6 contract, cheap checks first: `check_pdf.py` (structural), then `pdftoppm -jpeg -r 100 out.pdf page`, then `inspect_sandbox_images` over every page, then the same tool with `mode="together"`, then fix the source and repeat, and only then `save_artifact`. Both scripts ship as this skill's own `scripts/`. `check_pdf.py` grows past its current blank-page check to everything pypdf can measure — text outside the media box or margins, near-blank pages, page count against expectation, unembedded fonts — because each of those is a vision call the loop no longer has to spend.
- Subagent system prompt gains format-selection guidance (master spec §6.2) and demotes `generate_report`/`generate_resume` to "only when the user explicitly declines a file".

### 2.5 Frontend

- `PdfFileViewer` registry entry: existing `pdf-viewer.tsx` (move to `components/shared/pdf-viewer.tsx`; report panel imports from the new path) pointed at the primary file's `content_url`, lazy-loaded.
- Artifact card format badge for `application/pdf`.

### 2.6 Verification-loop architecture

The whole mechanism lives in this phase; later phases add format skills that use
it and nothing else. The test of that boundary: adding a format must need only a
`SKILL.md`, its own `scripts/`, and a viewer registry entry.

**The contract.** Generate → measure → render evidence → inspect → fix → repeat →
only then `save_artifact`; never save before verifying (master spec §6.3). Two
shapes are permitted and a skill states which it uses: *visual* (rasterize to
JPEG, review with `inspect_sandbox_images`) or *programmatic* (read values back
and assert). `pdf` in §2.4 is the reference implementation of the visual shape.
Two shapes is the whole taxonomy — "compare the output against the source data"
is the programmatic shape with a better assertion, not a third kind.

**The contract is enforced, not requested.** "Never save before verifying" as
prose means one copy of the rule per skill and zero places that check it, which
is the wrong medium for the one invariant every format shares. `save_artifact`
holds it instead (§2.3), so a new skill inherits the guarantee and its prose
shrinks to the genuinely format-specific part: how to render evidence for this
format and what to look for in it.

**Page count changes how much work happens, never what work happens.** That is
the whole granularity rule. Every page gets the measurable check, then individual
review, then windowed comparison — identically at one page and at forty. Cost is
linear in the artifact, which is proportionality rather than a problem to
optimize away: a ten-page document costs ten pages of verification because it is
ten pages of document. Any rule that varies with length — a batching threshold, a
"risky pages" sample — is a judgment the model applies silently wrongly, and
buying back tokens with a heuristic trades correctness for a bill.

The one asymmetry is *generation*, which is incremental only where units are
independent: slides and worksheets yes, a flowing PDF no, since pagination is
emergent and nothing is "page 2" until the whole document renders.

**Cheap checks first, and they measure different things.** The structural script
and the vision pass are not the same check at two prices. Whatever can be
measured — text past the margins or media box, blank and near-blank pages, page
count, missing embedded fonts — is measured mechanically on every page before any
vision call, so a defect in that class never costs a model round-trip. Vision
then answers only what cannot be measured: hierarchy, spacing, alignment,
legibility, factual consistency. This ordering is why the loop's step list starts
with the structural check.

**The shared surface is the tool, not the scripts.** `inspect_sandbox_images`
accepts JPEG only at 5 MB per image, owns fan-out and windowing, and rejects
anything else with an actionable error — so a skill cannot silently render
something incompatible, and cannot get the granularity wrong because it never
chooses it. Skills therefore stay self-contained: each ships
its own `{skills_root}/<name>/scripts/` as `pdf` does, with no cross-skill paths
and no shared directory competing with real skills under `/opt/skills/`.
Duplicating a 15-line rasterizer is cheaper than an indirection every skill
depends on, and it leaves room for genuine per-format differences (per-slide
naming, a conversion step first). <!-- ponytail: copies over a shared script;
ceiling is a fix landing in N skills, and the tool's input check is what stops a
stale copy from breaking the loop -->

**The roster stays prose, but a check owns it.** The deliverables system prompt
names `pdf` in prose and hardcodes `cat /opt/skills/pdf/SKILL.md`, so three more
formats mean prose edits in the file least likely to be reviewed next to the
skill, and nothing ties the list to what is installed. The fix is not to move the
roster into the image and read it per turn: Level 1 is by definition always in the
prompt (master spec §6.2), and fetching it from the sandbox would mean booting a
sandbox before the model knows whether it needs one. Instead the prompt keeps the
roster and a test asserts it matches the frontmatter under
`docker/sandbox/skills/*/` — same source that goes into the image, same repo, no
runtime cost. Adding a format that forgets the prompt then fails CI instead of
shipping a skill nothing advertises. <!-- ponytail: a test, not generated prompt
text; ceiling is the roster still being written by hand, and the test is what
makes that safe -->

The prompt's `cat /opt/skills/<name>/SKILL.md` line generalizes by parameter
rather than by enumeration, so Level 2 needs no edit per format either.

**What not to build.** A single `verify_artifact(path)` tool that renders and
inspects internally looks like the extensible move and is the opposite of one. It
hides the steps behind one opaque call, which is precisely the display this phase
still owes (below), and it can only do half the loop — fixing requires the model
to edit source, so the tool would return findings and hand control straight back,
having bought nothing and lost the visibility. The loop stays a sequence of
visible calls.

The boundary that makes fan-out and windowing not the same mistake: the tool
hides *how many vision calls one inspection takes*, which is arithmetic nobody
learns anything from, while every step the user cares about — generate, measure,
inspect, fix — stays a separate call in the timeline.

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
- Integration: "create a one-page PDF listing 3 facts about X" end-to-end → verified PDF renders in panel, ETag-cached on second open, downloads with correct filename. The assertion that the §2.6 loop actually ran (render and inspect steps present in the trace) belongs to this harness, parameterized as `(skill, prompt, expected MIME, expected evidence steps)` so a later format adds a row rather than a file — if adding `pptx` means writing a new test, the §2.6 boundary leaked and the test says where.
- Gate: `save_artifact` refuses a file regenerated after its last verification, and accepts it once re-verified. This is the one test that fails if the §2.6 contract silently degrades back into advisory prose. Its pair: with no vision model configured, the save **succeeds** and the recorded reason names the unavailability — the "could not verify" branch is what keeps the gate from turning a misconfigured workspace into a workspace that cannot produce artifacts at all.
- Roster: the prompt's Level 1 listing matches the frontmatter under `docker/sandbox/skills/*/` (§2.6).
- Revision, run twice against the same harness with the knowledge store on and off, because the two modes reach the artifact's path by different routes and only one of them has a projection to stamp the marker: generate, then ask for a change in a later turn → **one** document, its id unchanged, the primary file replaced, the superseded blobs gone, and the source read back rather than the document rebuilt. A second chat's roster must not name the first chat's artifact — that assertion is what catches an id captured at graph-build time, which passes every single-chat test. Revision rides the same parameterized harness as the loop assertion, for the same reason: nothing in it is PDF-shaped, so a later format proves it by adding a row, and needing a new file would mean the generality was lost somewhere.
- `inspect_sandbox_images` granularity, which is where a length-dependent regression would hide: `mode="each"` over 25 paths makes 25 single-image calls concurrently and returns 25 labelled findings; `mode="together"` over 25 makes 2 windowed calls; one path in `together` reports nothing to compare. A failure on one page leaves the other findings intact. The vision model resolves once across all of them.
- Regression: legacy `generate_report` path still functional (it isn't removed until phase 4).

---

## 3. Exit criteria

1. Spike numbers recorded in this file (create/warm-exec/read latencies) — §7.3 of the master spec becomes "verified in SurfSense".
2. "Create me a resume as a PDF" → model picks pdf skill → generates → visually verifies (page images demonstrably read by the model in the trace) → `save_artifact` → renders in panel, downloadable, KB-searchable. Zero Typst involvement.
3. Sandbox lifecycle: session reused within a thread (warm exec < 150 ms), reaped after idle TTL, capped per workspace with a clean error.
4. Self-hosted compose up works on a machine with no KVM and no cloud credentials.
