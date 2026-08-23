# Phase 2 — The `video` skill + agent wiring

**Status:** DESIGN.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Depends on:** Phase 1 (harness in the image); the deliverables sub-agent (`app/agents/chat/multi_agent_chat/subagents/builtins/deliverables/`).

## 1. Goal

The deliverables agent authors a video the same way it authors a PDF: load the skill, `execute` render code in the sandbox, self-review stills, iterate, then `verify_artifact` → `save_artifact`. No dedicated video tool.

## 2. The skill — `docker/sandbox/skills/video/SKILL.md`

A trusted instruction file (baked into `/opt/skills/video/` by the existing skills copy in `docker/sandbox/Dockerfile`). It encodes taste + the loop, mirroring `docker/sandbox/skills/{pdf,pptx}/SKILL.md`:

- **Composition rules:** 1920×1080 @ fps 30; safe outer margins; body contrast; motion timing/easing; one purpose per slide; keep shapes on-canvas; the SurfSense watermark is supplied by the harness (do not re-add).
- **Typography — pick from exactly three baked families, nothing else.** The jail has no network, so any other font silently falls back to a default and ships a wrong-looking video that structural verify won't catch (Phase 1 §2a). Reference them by `fontFamily` name only (they are system-installed; no `loadFont`/`@font-face`/`@remotion/google-fonts`):
  - **`Inter`** — default sans: body copy, most headings, UI-style slides.
  - **`Lora`** — serif: editorial titles, quotes, contrast.
  - **`JetBrains Mono`** — monospace: code, figures, data labels, tabular numerals.
  The skill must state these are the *only* permitted families and that requesting another is not possible offline.
- **Authoring contract:** write each slide as a Remotion component; imports from the baked `node_modules` are allowed (real bundler). The harness supplies `stagger` and standard `remotion` symbols via the preamble.
- **Narration:** call `synthesize_narration` (Phase 3) for the slide transcripts; it writes audio into the render workdir's `public/` and returns filenames. Reference them in `props.json`; do not fetch audio yourself (no network).
- **The loop:**
  1. **draft the deck spec first** — per-slide on-screen text **and** the narration line for each slide. This is both the render plan and the eventual `markdown_representation`; author from it, never reconstruct it from the finished video;
  2. turn each spec slide into a Remotion scene + `props.json`; the narration lines are what you pass to `synthesize_narration`, referencing the returned audio from `props.json`;
  3. `execute` `node render.mjs --stills props.json /tmp/stills` and review the PNGs (`read_sandbox_file` is text-only, so review via the verify/vision path or re-render);
  4. fix and re-run stills until they pass the skill's checklist;
  5. `execute` the full render → `/workspace/out.mp4`;
  6. `verify_artifact(path="/workspace/out.mp4")`;
  7. `save_artifact(path=..., title=..., markdown_representation=<the step-1 deck spec>)` — carry that spec through **unchanged** (per-slide content **and** narration), not a blurb summarized after the fact. It is the only durable, editable representation of the video — the scene components and `props.json` are ephemeral sandbox files that are never persisted — so it doubles as search/accessibility text **and** the source a later revision regenerates from (§4, Revision).
- **Constraints:** never `npm install` / download (everything baked); a single render must fit `SANDBOX_OPERATION_TIMEOUT_SECONDS` — for long decks the harness renders in segments and `ffmpeg concat`s them (the knobs and rationale are §5, Render sizing & concurrency).

## 3. The rollout flag (the on/off switch)

The whole legacy-vs-new choice is one boolean, so the new path can be shipped dark, enabled per-env, and rolled back without a deploy.

- **Definition** — `app/config` (mirroring the existing `*_ENABLED` flags such as `SANDBOX_ENABLED`):

  ```python
  # app/config/__init__.py
  VIDEO_SANDBOX_RENDERING_ENABLED = (
      os.getenv("VIDEO_SANDBOX_RENDERING_ENABLED", "FALSE").strip().upper() == "TRUE"
  )
  ```

  Document the key in `surfsense_backend/.env.example`. Default `FALSE` ⇒ **today's LangGraph path runs, unchanged**.

- **Semantics** — the flag gates the **authoring entrypoint only**. `TRUE` ⇒ the deliverables agent gets the skill loop (this phase) + `synthesize_narration` (Phase 3); `FALSE` ⇒ it gets the legacy `create_generate_video_presentation_tool`. The Phase-4 adapter, Phase-5 persistence/serving, and the Phase-6 `<video>` renderer are all **flag-agnostic** (additive, inert until an MP4 exists), so nothing else branches.

## 4. Wiring

- **`deliverables/tools/index.py::load_tools`** — the single switch point. Register the legacy tool **or** the new narration bridge by the flag; the shared `execute`/`verify_artifact`/`save_artifact` are always present, so authoring needs **no new tool** on the new path:

  ```python
  from app.config import config

  if config.VIDEO_SANDBOX_RENDERING_ENABLED:
      tools.append(create_synthesize_narration_tool(          # Phase 3
          workspace_id=d["workspace_id"], db_session=d["db_session"]))
  else:
      tools.append(create_generate_video_presentation_tool(    # legacy (deleted in Phase 8)
          workspace_id=d["workspace_id"], db_session=d["db_session"]))
  ```

- **`deliverables/tools/sandbox.py`** — extend `load_artifact_instructions`'s `Literal["pdf","docx","pptx","xlsx"]` to include `"video"` so it `cat`s `/opt/skills/video/SKILL.md`. Safe to land unconditionally (the skill is only reached when the flag routes video work to it).
- **Revision — `deliverables/tools/load_artifact_for_revision.py`** — add a `"video"` entry to `_REVISION_INSTRUCTIONS`. Video is **regenerate-from-markdown** (the `pdf` family, not the byte-editable `docx`/`pptx` family): the MP4 is not editable in place and the scene source is not persisted, so a "make it better" request re-authors the deck from the saved spec and re-renders. The entry instructs exactly that — e.g. *"Regenerate the video: re-author the deck from `markdown_path` plus the user's new instruction, re-render to the expected output path, then re-verify. Do not attempt to edit `current.mp4` — it is restored for reference only."* The rest is the shared revision loop, unchanged: `load_artifact_for_revision` restores the current MP4 **and** the deck-spec markdown (from `document.source_markdown`, which is always stored independent of KB indexing), the model re-renders + `verify_artifact`s, and `save_artifact(artifact_id=..., expected_generation=...)` replaces it in place as a new generation. Additive and safe to land unconditionally (only reached for an existing `video` artifact). As with PDF, exact visual layout may drift across a revision because it regenerates from the spec rather than editing pixels — the accepted trade-off for not persisting scene source (deferred, umbrella §8).
- **Prompt routing — `deliverables/agent.py`** — the system prompt is static markdown (`read_md_file(__package__, "system_prompt")`), so make routing **flag-aware at compose time** rather than editing the base file to point at one path: when `VIDEO_SANDBOX_RENDERING_ENABLED` is on, append a small "video → skill loop" routing block; when off, the base prompt keeps today's `generate_video_presentation` guidance. This keeps the prompt consistent with the tool that is actually registered.

## 5. Render sizing & concurrency

The in-turn render is bounded by `SANDBOX_OPERATION_TIMEOUT_SECONDS` per `execute` call. Three knobs make the render fit that budget deterministically **and** carry over unchanged if rendering later moves to the deferred queued fleet (umbrella §4) — they are durable capacity controls, not stopgaps:

- **`VIDEO_SANDBOX_MAX_FRAMES_PER_SEGMENT` (config).** Sized from measured render throughput (frames/sec on the target hardware, captured by the Phase-1 spike) so one segment renders at ~60–70% of `SANDBOX_OPERATION_TIMEOUT_SECONDS`, leaving headroom for `bundle()` + Chrome launch + variance. The **harness** (not the model) splits any deck beyond this bound into back-to-back segment renders and joins them with a stream-copy `ffmpeg concat` (the system ffmpeg baked in Phase 1 §2 — no re-encode, so the join is near-free). Segmentation stays useful under the queued fleet too: segments render in parallel and retry cheaply and independently.
- **Product length cap — reuse `VIDEO_PRESENTATION_MAX_SLIDES`.** Maximum deck length is a deliberate *product* ceiling — the same one today's browser-rendered path already enforces — not a timeout artifact. The skill **refuses** a request past it with a clear message instead of attempting an unreasonable multi-segment render. This stays a product decision across the inline→queued flip.
- **`VIDEO_SANDBOX_MAX_CONCURRENT_RENDERS` (admission gate).** A video render holds its sandbox slot for the whole (long) render, so concurrent renders pass through a bounded gate sized to fleet capacity: a burst **queues** rather than exhausting the fleet into timeouts (umbrella §3). This is the one value whose *implementation* changes but whose *meaning* does not across the flip — a gate today, the render worker-pool concurrency later.
  - **The gate must bound the *fleet*, not one process.** A bare in-process `asyncio.Semaphore` bounds a single API worker; with `W` workers/pods you get `W × N` concurrent renders — the exact fleet exhaustion the gate exists to prevent. Two acceptable shapes: **(a)** keep the semaphore in-process but define the knob as *per-worker* and size the sandbox fleet to `W × N` (document that scaling workers re-sizes the fleet); or **(b)** a **distributed limiter** (Redis lease/token) so `N` is a true global ceiling regardless of `W`. Given SurfSense already runs Redis (Celery), (b) is the honest choice for a real fleet; (a) is acceptable only while `W` is fixed and known. This distinction is invisible today but silently wrong the moment the API runs more than one worker — call it out so it isn't discovered under load.

All three live in `app/config` alongside `VIDEO_SANDBOX_RENDERING_ENABLED` and are documented in `surfsense_backend/.env.example`.

## 5a. Render telemetry (make the inline→queued flip a data decision)

The umbrella defers the queued render fleet "if sustained concurrency outgrows the sandbox fleet" (§4) — but nothing measures that today, so the decision would be guesswork. Emit metrics from the first inline render so the threshold is observed, not vibed:

- **`render_seconds`** (per render; and per segment for long decks) — throughput drift vs. the Phase-1 spike; feeds `VIDEO_SANDBOX_MAX_FRAMES_PER_SEGMENT` re-sizing.
- **`admission_queue_wait_seconds`** + **current gate depth** — the primary signal that the gate is saturating and the fleet needs the queued shape.
- **`segment_count`** per deck — how often long-deck segmentation actually triggers.
- **`verify_fail_total{reason}`** — structural vs. frame-sanity vs. concat-duration (Phase 4), so silent-failure classes are visible.

Reuse the existing observability sink (whatever `app/observability` already exports); these are counters/histograms, not a new subsystem.

## 6. Language guarantee (unchanged)

Rendering runs through `execute(language="bash")` invoking `node render.mjs`. The `execute` schema stays `Literal["python","bash"]`; JS/TS is authored as files and run via Node under bash. No new language surface is exposed.

## 7. Checks

- Unit: `load_artifact_instructions("video")` returns the skill body (mirror the existing skill-load contract test).
- Flag off (default): `load_tools` registers `create_generate_video_presentation_tool` and **not** `synthesize_narration`; a video request drives the legacy path (regression guard — existing behavior is untouched).
- Flag on: `load_tools` registers `synthesize_narration` and **not** the legacy tool; a "make a video" request drives `load_artifact_instructions("video")` → `execute` (stills) → `execute` (mp4) → `verify_artifact` → `save_artifact`, with no Celery dispatch and no `generate_video_presentation` call.

## 8. Exit criteria

1. `VIDEO_SANDBOX_RENDERING_ENABLED` toggles the authoring path with no other code change; off preserves today's LangGraph behavior exactly.
2. The video skill is present in the image and loadable by the agent.
3. With the flag on, the deliverables prompt routes video work to the skill loop.
4. A flag-on model run produces `/workspace/out.mp4` using only `execute` + the baked harness.
