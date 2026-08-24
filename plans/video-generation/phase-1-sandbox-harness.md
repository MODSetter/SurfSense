# Phase 1 — Sandbox Remotion harness + Chrome

**Status:** DESIGN.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Depends on:** the existing sandbox image and provider.

## 1. Goal

Provide an offline, deterministic harness that turns typed, complete LLM-authored TSX scene modules plus trusted props/audio into:

- native bundle/metadata preflight diagnostics;
- start/middle/end stills for every scene and one contact sheet;
- one narrated MP4;
- atomic progress suitable for a durable queued job; and
- cooperative cancellation with partial-output cleanup.

The harness executes only inside a fresh job-owned sandbox. The entire video workflow is driven by the deliverables subagent in trusted `queued_job` mode; this phase does not define an inline/chat-turn renderer.

## 2. Image contract

Graft the official Remotion Docker requirements onto the existing `opensandbox/code-interpreter` base; do not replace it with `node:22-slim`. Bake:

- exact, matching stable versions of `remotion`, React, `@remotion/bundler`, `@remotion/renderer`, `@remotion/media`, and `@remotion/media-parser`;
- Chrome Headless Shell via `npx remotion browser ensure`;
- system ffmpeg/ffprobe for structural checks and cleanup validation;
- the render harness and all `node_modules`, so runtime never installs or downloads;
- the closed offline font palette already selected for the video skill: Inter, Lora, and JetBrains Mono.

Keep the code-interpreter entrypoint. Rendering is invoked per queued job through the sandbox provider. Network remains denied.

This image is the sandbox image that executes generated TSX. The dedicated `video_render` Celery worker is a separate Compose service that reuses the existing backend/Celery image; no new worker image is introduced.

## 3. Scene and project-writing contract

Every generated scene is a complete, self-contained `.tsx` module:

```tsx
import React from "react";
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export default function Scene() {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const opacity = interpolate(frame, [0, 12, durationInFrames - 12, durationInFrames], [0, 1, 1, 0]);

  return (
    <AbsoluteFill style={{ backgroundColor: "#0b1020", color: "white", opacity }}>
      <h1 style={{ margin: 120, fontFamily: "Inter", fontSize: 88 }}>Example scene</h1>
    </AbsoluteFill>
  );
}
```

Requirements:

- imports are explicit;
- a default export is mandatory;
- modules are written verbatim;
- any layout is allowed within output/safe-margin policy;
- generated modules do not depend on injected globals;
- no regex parsing, source rewriting, import stripping, export promotion, or fixed slide template exists.

A trusted `prepare_video_project` deliverables tool accepts typed scene objects and trusted metadata. It writes files with `SandboxSession.write_file()` and serializes `props.json` as JSON. It never constructs TSX with Python f-strings or passes scene source through shell quoting.

Representative trusted input:

```json
{
  "fps": 30,
  "scenes": [
    {
      "scene_number": 1,
      "module_filename": "scene-001.tsx",
      "audio_filename": "scene-001.mp3"
    }
  ]
}
```

Scene code is stored in its module file, not duplicated in `props.json`.

## 4. Remotion project

The baked project registers one 1920×1080 composition. `calculateMetadata()` measures the exact narration bytes that will be muxed, computes per-scene durations, and returns resolved props and total frames. The deck sequences scenes and their audio without reconstructing or rewriting scene source.

The harness exposes:

```text
node render.mjs --preflight props.json
node render.mjs --stills props.json outdir/
node render.mjs props.json out.mp4
```

All modes share the same input loading, `bundle()`, `selectComposition()`, bundle cache, progress format, cancellation behavior, Chrome options, and bounded per-frame delay-render timeout.

### 4.1 Native preflight

`--preflight`:

1. validates trusted props and referenced files;
2. bundles the real project with esbuild/Remotion;
3. calls `selectComposition()` so `calculateMetadata()` runs;
4. verifies dimensions, fps, scene count, audio references, and selected duration;
5. returns concise structured diagnostics tied to scene number/module filename.

Missing/malformed default exports fail through the bundler. Diagnostics may classify native errors, but must not inspect or transform source with regular expressions.

### 4.2 Product gates

Version-controlled policy allows at most:

- 12 scenes; and
- 180 seconds of final output.

Enforce duration twice:

1. after narration, reject measured transcript/audio total above 180 seconds;
2. after `selectComposition()`, reject `composition.durationInFrames / composition.fps > 180` before any still or `renderMedia()` call.

The exact 180-second boundary is valid. Product limits are distinct from the queued worker's bounded soft/hard execution budget.

### 4.3 Exact-input bundle reuse

Hash all complete module bytes, props, and other bundle-affecting inputs with Node's `crypto` SHA-256. Cache the resulting bundle only inside the trusted job workdir. Reuse it between preflight, still review, and final render only on an exact hash match.

No cross-job cache is required. Changed module/props input must invalidate the cache.

### 4.4 Multi-frame visual review

For each scene, render representative start, middle, and end frames based on the resolved cumulative timeline, plus one contact sheet. Stills use the same selected composition and exact-input bundle as final rendering.

The queued deliverables subagent reviews them through a bounded `review_video_stills` tool using the existing configured vision model when available. The rubric covers clipping, overflow, contrast, hierarchy, blank frames, motion endpoints, and safe margins. It does not impose a template or fixed layout.

### 4.5 Progress and cancellation

`renderMedia({ onProgress })` writes a small progress snapshot atomically (temporary file then rename). The payload is trusted machine state, for example:

```json
{"phase":"rendering","rendered_frames":900,"total_frames":2700,"fraction":0.3333}
```

A worker-side monitor maps this to job progress and checks the database for `cancelling`. When requested, it writes a trusted cancel marker into the job workdir. The harness checks that marker from `onProgress` and calls Remotion's `makeCancelSignal()` cancellation path.

Handle SIGTERM/SIGINT cooperatively. In `finally`, remove partial segments, temporary stills, and incomplete MP4 output while retaining only inputs/checkpoints explicitly needed for a permitted retry. Cancellation must stop before verification and save.

## 5. Runtime ownership and cleanup

Before agent invocation, the queued worker creates a fresh sandbox and a trusted workdir such as `/workspace/deliverable-job-{job_id}`, then copies the baked harness. Sandbox ownership is `deliverable-job:{job_id}` and is separate from root-thread Artifact attribution.

The model cannot choose the workdir, cancellation marker, progress path, or cleanup root. Two jobs from the same chat never share a sandbox or checkpoint namespace.

The worker terminates the job-owned sandbox in `finally`. Cleanup errors are logged but cannot overwrite a ready, failed, or cancelled state transition.

## 6. Checks

- A complete two-scene default-export fixture passes preflight, emits three frames per scene plus a contact sheet, and renders an audible 1920×1080 MP4 offline.
- Missing and malformed default exports fail through bundling with scene/file diagnostics.
- A repository search/test proves the harness has no source regex or `prepareSource()` transformation.
- Typed preparation preserves module bytes exactly and safely serializes props.
- 180 seconds passes; any positive amount above it fails before rendering.
- Exact inputs reuse a bundle; one-byte module/props changes invalidate it.
- Progress snapshots are atomic and monotonic enough for the worker mapping.
- A cancel marker interrupts an active real Chrome render and leaves no partial MP4.
- The review set includes start/middle/end for every scene and one contact sheet.

## 7. Exit criteria

1. The sandbox image builds and Chrome launches with network denied.
2. Native preflight is the only compile contract; there is no regex scene rewriting.
3. Product duration/scene gates run before expensive rendering.
4. Preflight, stills, and final render reuse an exact-input bundle.
5. Real rendering publishes progress and responds to cooperative cancellation.
6. A playable, narrated MP4 is produced by the queued-job harness path.
