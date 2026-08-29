# Phase 1 — Sandbox Remotion harness + Chrome

**Status:** IMPLEMENTED.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).

## 1. Outcome

The existing `opensandbox/code-interpreter` image now includes an offline Remotion project that converts trusted typed inputs and complete generated TSX scene modules into preflight diagnostics, review stills, and one narrated 1920×1080 MP4.

The harness is invoked by the backend video executor inside an attempt-owned sandbox. It is not an inline browser renderer and is not driven by a queued subagent.

## 2. Image and project contract

`docker/sandbox/Dockerfile` bakes:

- Node/React/Remotion dependencies from `docker/sandbox/remotion/package.json`;
- Chrome Headless Shell through Remotion's browser setup;
- system ffmpeg/ffprobe;
- the Remotion harness and installed `node_modules`;
- Inter, Lora, and JetBrains Mono for offline use.

The code-interpreter entrypoint remains unchanged and generated code executes with sandbox networking disabled.

`docker/sandbox/remotion/src/Root.tsx` registers composition `Main` at 1920×1080 and 30 fps. `calculateMetadata()` probes narration audio, resolves scene durations, and computes the total frame count. `Deck.tsx` sequences each scene with its audio and adds the shared SurfSense icon watermark from `public/icon-128.svg`.

## 3. Scene input and deterministic preparation

Every generated scene is a complete module with explicit imports and a default export. The system does not strip imports, promote exports, inject globals, parse source with regexes, or force a fixed slide template.

The backend assigns:

- sequential scene numbers;
- `scene-NN.tsx` module filenames;
- corresponding narration filenames;
- scene order and stable metadata.

`prepare_video_project()` validates the authored schema and writes `props.json` with `SandboxSession.write_file()`. The current props include each scene's complete source code; `render.mjs` validates the payload and writes those modules into `src/scenes/` before bundling. Generated code is never interpolated through shell commands.

## 4. Harness commands

```text
node render.mjs --preflight props.json
node render.mjs --stills props.json outdir/
node render.mjs props.json out.mp4
```

All modes share validation, scene writing, bundling, composition selection, Chrome settings, and exact-input bundle reuse.

### Preflight

Preflight:

1. validates props, scene count, and referenced audio;
2. writes the generated scene modules;
3. validates modules with esbuild;
4. bundles the real Remotion project;
5. runs `selectComposition()` and `calculateMetadata()`;
6. enforces dimensions, fps, and the selected duration limit;
7. returns bounded diagnostics.

### Still review assets

Stills mode renders start, middle, and end frames for every scene and creates one ffmpeg contact sheet. The backend sends these files to `review_video_stills()` when a vision model is available.

### Final rendering

Full mode renders bounded frame segments and concatenates them into the requested MP4. Temporary output retains an `.mp4` suffix so ffmpeg can select the output format. A `.segments.json` sidecar records expected segment timing for final verification.

## 5. Product and runtime bounds

- maximum 12 scenes;
- maximum selected duration 180 seconds;
- exact 180 seconds is valid;
- `VIDEO_SANDBOX_MAX_FRAMES_PER_SEGMENT` controls segment size;
- `VIDEO_SANDBOX_RENDER_FRAME_TIMEOUT_MS` controls bounded frame timeout;
- `VIDEO_SANDBOX_MAX_CONCURRENT_RENDERS` gates concurrent full renders per worker process.

These render settings are existing configuration, while scene count, duration, repair count, and Celery task limits are defined by `DeliverableKindSpec`.

## 6. Ownership, progress, and cancellation

Each attempt uses:

```text
owner:   deliverable-job-{job_id}-attempt-{attempt_count}
workdir: /workspace/deliverable-job-{job_id}-attempt-{attempt_count}
output:  /workspace/deliverable-job-{job_id}-attempt-{attempt_count}.mp4
```

`render.mjs` atomically writes `progress.json`, supports a cancel marker, reacts to SIGTERM/SIGINT through Remotion cancellation, and removes partial output in cleanup.

The current Celery implementation uses stage-level database heartbeats. Its cancellation watcher cancels the executor task and terminates the attempt sandbox; it does not currently poll `progress.json` or write the harness cancel marker.

The task always attempts sandbox termination in `finally`. Cleanup failures are logged and do not replace the job's lifecycle result.

## 7. Implemented checks

- native bundle and composition preflight;
- typed scene/project validation;
- exact-input bundle invalidation;
- 12-scene and 180-second gates;
- start/middle/end still generation and contact sheet;
- segmented MP4 rendering with audio-derived timing;
- atomic progress snapshots and cancellation primitives;
- structural verification exercised by the backend pipeline.

Frame-level progress integration and a real-browser cancellation integration test remain optional hardening work; they are not part of the current worker behavior.
