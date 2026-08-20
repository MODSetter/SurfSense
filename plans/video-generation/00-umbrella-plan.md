# Sandbox-Native Video Generation — Umbrella Plan

**Status:** DESIGN. No phase implemented yet.
**Scope:** Replace the monolithic `generate_video_presentation` LangGraph + browser-side Remotion rendering with a **skill-driven, sandbox-executed, verify-in-the-loop** deliverable that outputs a single MP4 stored in blob and streamed to a plain `<video>`.
**Shape:** Video becomes one more deliverable on the existing artifact machinery (`execute` → `verify_artifact` → `save_artifact`), the same pattern as PDF/DOCX/PPTX/XLSX ([`../artifacts/artifacts-overhaul.md`](../artifacts/artifacts-overhaul.md), [ADR 0003](../../docs/adr/0003-artifacts-as-documents.md)).

This document is the authoritative architecture. Phase documents record delivery scope and must not override these contracts.

## 1. Why

Today's video path is the one deliverable that breaks every pattern the artifact system established:

- **Untrusted code runs in the user's browser.** `surfsense_web/lib/remotion/compile-check.ts` transpiles LLM-authored scene code with Babel and executes it with `new Function(...)`. That is arbitrary code execution on our origin, per view.
- **No quality loop.** `app/agents/video_presentation/` generates scene code **once**, never runs it, never looks at a frame, and ships `scene_codes` + per-slide audio to the browser to render blind. PDF/DOCX get their quality from render → vision-check → fix; video gets none of it.
- **A parallel subsystem.** A bespoke Celery task, graph, `record.py`, and per-slide audio storage/endpoints exist only to feed the browser renderer, duplicating persistence/serving that the artifact system already owns.

## 2. Target architecture

Three zones, one trust boundary:

| Zone | Trust | May access | Job |
|---|---|---|---|
| Deliverables agent (LLM) | Trusted | LLM/TTS APIs, DB, billing, blob | Authors scene code, drives the loop |
| Sandbox (OpenSandbox) | Untrusted-code jail | **Nothing** — network denied, no creds | Bundles + renders + verifies model code → MP4 |
| Browser | Client | Only finished artifact bytes | Plays one inert MP4. Renders nothing. |

**Invariant:** the model's inference and any network-bound API (LLM, TTS) run trusted-side; **all build/compile/render/verify code runs inside the sandbox** (bwrap + seccomp, `NetworkPolicy(default_action="deny")`); the browser only ever receives an inert MP4.

### The agentic loop (what "creating a slide" now means)

```
1. author    model writes a scene's Remotion component        (trusted side)
2. narrate   synthesize_narration tool → audio into public/   (trusted side, network)
3. execute   render one still per slide (renderStill → PNG)    ← cheap, in sandbox
4. verify    vision-check stills: overflow, contrast, pacing   ← model self-review
5. iterate   fix code, re-run stills                           ← fast: images, not video
6. render    once stills pass → ONE full MP4 (renderMedia)      ← in sandbox
7. verify    verify_artifact on the final MP4 → signed receipt  ← binds bytes
8. save      save_artifact → MP4 as PRIMARY → blob
```

## 3. Decisions locked

- **No templates.** The harness is a fixed *frame* (1920×1080, fps 30, slide sequencing, audio mux, watermark), not a design mold. The model authors a full component per slide. With a real bundler it may use real `import`s from the baked `node_modules`, so it is *freer* than the old injected-globals browser path.
- **Skill, not tool.** Video is authored by following `/opt/skills/video/SKILL.md` via the existing `execute`/`verify_artifact`/`save_artifact` tools — there is no dedicated `generate_video` tool. Mirrors documents exactly.
- **Chrome is non-negotiable.** Remotion renders DOM via headless Chrome; there is no browserless renderer. Use `chromeMode: 'headless-shell'` (the lightest browser Remotion supports), baked via `npx remotion browser ensure`. WebCodecs (`@remotion/web-renderer`) is still a browser and runs client-side — rejected.
- **We follow official SSR.** The harness is the Remotion Node SSR path (`@remotion/bundler` `bundle()` + `@remotion/renderer` `renderMedia()`), i.e. the `/docs/docker` `render.mjs`. We graft its Chrome dep list + `npm i` + `browser ensure` onto the **`opensandbox/code-interpreter` base**, not `node:22-slim` (that base already carries Node 22 + Python/bash/kernels/skills the rest of the sandbox needs).
- **Audio drives timing, and is mandatory.** The deliverable is a narrated MP4, never a mute video. Narration is generated trusted-side (TTS needs network, reusing today's `create_slide_audio`), written into the render workdir's `public/`, and referenced via `staticFile()`. Timing is owned by Remotion's `calculateMetadata`: each slide's audio is measured with `parseMedia` (the non-deprecated, cross-platform successor to `getAudioDurationInSeconds`) and its `durationInFrames = max(ceil(seconds·fps), floor)` for exact sync. `renderMedia` muxes the narration into the single MP4 (no separate audio stream), and Phase-4 verification hard-fails an MP4 with no audio stream — so a mute video can never be saved.
- **Verify binds the final bytes.** `save_artifact` only accepts a `path` whose bytes match a signed `verify_artifact` receipt keyed by `get_format_adapter(path).name`. So video needs a `video` format adapter and a verify strategy (ffprobe structural + sampled-frame vision) run against the final MP4. The cheap per-slide stills are a model-side iteration aid, not the receipt gate.
- **Reuse persistence/serving.** MP4 is the PRIMARY `ArtifactFile`; `save_artifact`/`persist_artifact` already offload PRIMARY blobs. Serving reuses `stream_artifact_file` with HTTP Range added. No parallel media system.
- **Execution is awaited in-turn, bounded by admission control.** The render is not a detached background job — the deliverables agent `await`s the sandbox command inside its turn (asyncio-async, non-blocking to the event loop), so no status table or polling is needed; the saved+verified artifact is the durable record. Two consequences: (a) a single render must fit `SANDBOX_OPERATION_TIMEOUT_SECONDS` per `execute`, so long decks render in segments + `ffmpeg concat`; (b) because a video render holds a sandbox slot for its whole duration (long hold time, unlike short document renders), concurrent renders pass through a **bounded admission gate** (a semaphore sized to fleet capacity) so a burst *queues* rather than exhausting the fleet into timeouts. Document artifacts keep the plain in-turn path — their hold time is short enough that occupancy stays low (Little's law), so they need no gate.
- **Build seam is generic; only the builder is per-format.** Downstream is already format-agnostic — `verify_artifact` dispatches by `get_format_adapter(path).name`, and `save_artifact`/serving are format-neutral. The only video-specific code is the *builder* (scene code → MP4 via `render.mjs`). We name that seam — `ArtifactBuilder` (inputs → primary file in the sandbox) with a per-type `ExecutionMode` (`inline` today for everything) — so the future scale-out path (below) is reachable without reworking persistence or verify. Justified on **reuse, not throughput**: the seam adds no scaling by itself.

## 4. Deferred (out of this umbrella)

- **Image size optimization.** The sandbox image grows (Chrome + Remotion `node_modules`). Slimming the base (drop Go/Java/extra runtimes) and swapping `-dev` Chrome libs for runtime variants is a separate pass.
- **Signed-URL / CDN delivery.** Backend Range streaming ships first (works on every storage backend incl. local disk, keeps per-request auth). Direct-to-blob signed URLs + CDN are a later bandwidth/scale optimization for the read path, gated on `backend.supports_signed_urls()`.
- **Decoupled render fleet (scale-out target).** The in-turn model + admission gate is v1. If sustained concurrency outgrows the sandbox fleet, flip the video `ExecutionMode` to `queued`: the agent turn ends by *submitting* a render job (after the cheap in-turn stills loop), and a durable queue feeds an autoscaling pool of **stateless render workers** that run render → verify → `save_artifact`, marking the artifact `ready` asynchronously (status pushed via the existing Zero live-query / SSE, backed by a *lean, generic* render-job row — **not** a revival of `video_presentation_runs`). This is the maximally scalable shape (backpressure, horizontal workers, retries, survives disconnect, serving decoupled to storage/CDN) and is reachable **without reworking persistence/verify** thanks to the builder seam. Deferred because it adds a queue + workers + status push for hypothetical load; document artifacts can adopt the same `queued` mode later (reuse), which only then yields shared-fleet multiplexing efficiency.
- **GPU rendering** (`chrome-for-testing`) and Remotion Lambda/Cloud Run. Not needed for 2D slide rendering.

## 5. Phase index

| Phase | Subplan | Status |
|---|---|---|
| 1 | [`phase-1-sandbox-harness.md`](phase-1-sandbox-harness.md) — Remotion harness + Chrome in the sandbox image | DESIGN |
| 2 | [`phase-2-video-skill.md`](phase-2-video-skill.md) — the `video` skill + agent wiring | DESIGN |
| 3 | [`phase-3-narration-bridge.md`](phase-3-narration-bridge.md) — trusted-side TTS into the sandbox | DESIGN |
| 4 | [`phase-4-verification.md`](phase-4-verification.md) — video format adapter + verify strategy | DESIGN |
| 5 | [`phase-5-persistence-and-serving.md`](phase-5-persistence-and-serving.md) — MP4 primary, Range, inline mime | DESIGN |
| 6 | [`phase-6-frontend.md`](phase-6-frontend.md) — replace the browser renderer with `<video>` | DESIGN |
| 7 | [`phase-7-retire-legacy.md`](phase-7-retire-legacy.md) — delete the graph, Celery task, tool | DESIGN |
| 8 | [`phase-8-migration-backfill.md`](phase-8-migration-backfill.md) — backfill legacy video artifacts | DESIGN |

## 6. Sequencing

- **Critical path:** `1 → 2 → 4 → 5`. Harness proves the jail renders; skill wires authoring; verify+persist make one MP4 saveable end-to-end.
- **Parallelizable:** `3` (narration) can develop alongside `2`/`4`; the still-loop works on silent stills, audio only matters at final render + duration.
- **After the new path is green:** `6` (frontend to `<video>`), then `7` (retire legacy), then `8` (backfill).
- Recommended: `1 → 2 → 4 → 3 → 5 → 6 → 7 → 8`.

## 7. Cross-phase dependency deltas

- **Sandbox image (+):** Chrome libs (per `/docs/docker`), `remotion`, `@remotion/bundler`, `@remotion/renderer`, `@remotion/media`, `@remotion/media-parser`, baked Chrome Headless Shell.
- **Backend (+):** `video` format adapter + verify strategy; `synthesize_narration` tool; HTTP Range on `stream_artifact_file`.
- **Backend (−):** `app/agents/video_presentation/`, `video_presentation_tasks.py`, `deliverables/tools/video_presentation.py`, `artifacts/media/video/record.py` + `storage.py`, `/artifacts/{id}/video` + `/slides/{n}/audio` routes.
- **Frontend (−):** `@remotion/player`, `@remotion/web-renderer`, `@remotion/media`, `@babel/standalone`, `lib/remotion/compile-check.ts`, `combined-player.tsx`.
