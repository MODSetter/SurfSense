# Phase 1 — Sandbox Remotion harness + Chrome

**Status:** DESIGN.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Depends on:** the existing sandbox image (`docker/sandbox/Dockerfile`, `FROM opensandbox/code-interpreter:v1.1.0`) and provider (`app/sandbox/providers/opensandbox.py`).

## 1. Goal

The jail can turn arbitrary LLM-authored scene strings into (a) one still PNG per slide and (b) one MP4 with muxed audio — **offline**, following the official Remotion Node SSR path (`/docs/docker`).

## 2. Image changes — `docker/sandbox/Dockerfile`

Graft the official Remotion Docker layer onto the **existing** base (do **not** switch to `node:22-slim`; the code-interpreter base already carries Node 22 + Python/bash/kernels/skills/LibreOffice the rest of the sandbox needs). Add after the npm `docx` layer, before the skills copy:

```dockerfile
# ---- Remotion server-side render harness (Node 22 already in base) ----
# Chrome shared libraries — canonical list from Remotion /docs/docker — plus a
# system ffmpeg used for segment concat of long decks (Phase 2 §5). Remotion's
# own bundled ffmpeg handles render/mux (§3); concat is the one step that shells
# out to ffmpeg directly, so we add a binary on PATH. (Verify is structural-only
# — Phase 4 — so it needs no frame extraction.)
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        libnss3 libdbus-1-3 libatk1.0-0 libgbm-dev libasound2 libxrandr2 \
        libxkbcommon-dev libxfixes3 libxcomposite1 libxdamage1 \
        libatk-bridge2.0-0 libpango-1.0-0 libcairo2 libcups2 \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Bake the harness scaffolding + node_modules + Chrome so rendering needs no network.
ENV REMOTION_HOME=/opt/remotion
COPY remotion/ ${REMOTION_HOME}/
RUN set -euo pipefail \
    && cd ${REMOTION_HOME} \
    && npm install \
    && npx remotion browser ensure \
    && node -e "require('@remotion/renderer'); require('@remotion/bundler')"
```

Notes:
- `libpango-1.0-0` is already installed in the artifact layer — harmless duplicate (apt is idempotent).
- `-dev` variants (`libgbm-dev`, `libxkbcommon-dev`) match the doc exactly; downgrading to runtime `libgbm1`/`libxkbcommon0` is a **deferred** size pass.
- `chromeMode` stays default `headless-shell` (lightest). No `CMD` — the code-interpreter `ENTRYPOINT` is unchanged; renders are invoked per-call via `execute`/`run_command`.

## 3. New harness — `docker/sandbox/remotion/`

Baked at build time (scaffolding + deps only; scenes/audio are injected at runtime):

- **`package.json`** — `remotion`, `react`, `react-dom`, `@remotion/bundler`, `@remotion/renderer`, `@remotion/media` (the modern, Mediabunny-backed `<Audio>` — the recommended tag for new projects, not the legacy core `remotion` `<Audio>`), `@remotion/media-parser` (`parseMedia`, the non-deprecated successor to `getAudioDurationInSeconds`, used for duration probing in §4). FFmpeg ships inside `@remotion/renderer` for the render/mux step, so no apt ffmpeg is needed *for rendering* — but a system `ffmpeg` is still installed in §2 for the one step that shells out to it directly: **segment concat** for long decks (Phase 2 §5), which does not go through the renderer. Verify is structural-only (Phase 4), so it needs no frame extraction.
  - **Pin all Remotion packages to one exact version** (Remotion hard-requires `remotion` + every `@remotion/*` to be the *same* version; a floating `^` in a baked image risks a mismatched patch at build time). Install with `--save-exact` / `npx remotion add` so versions stay aligned. Target the latest **4.0.x** stable (4.0.514 at time of writing). **Do not adopt the 5.0 migration** — v5 is not the npm `latest` tag yet (only `4.1.0-alpha` prereleases exist); staying on 4.0.x keeps us on the released line.
- **`src/index.ts`** — `registerRoot(Root)`.
- **`src/Root.tsx`** — registers ONE `<Composition id="Main" component={Deck} calculateMetadata={calculateMetadata} />`. Even with `calculateMetadata`, v4 still **requires** the static `width={1920} height={1080}`, placeholder `fps={30}` and `durationInFrames={1}`, and a `defaultProps` (mandatory because `Deck` takes props) — `calculateMetadata` overrides `fps`/`durationInFrames` at render. `calculateMetadata` is Remotion's canonical data-driven-duration hook: it measures each slide's narration and returns the resolved `fps` + total `durationInFrames` and passes per-slide durations down via `props`, so timing is owned by Remotion's own metadata pipeline rather than hand-computed. Props are declared as a `type` (v4 forbids `interface` for composition props). `Deck` lays the slides out with `<Series>` (see §4).
- **`stagger.ts`** — server port of `createStagger` from `surfsense_web/lib/remotion/compile-check.ts` (keeps the injected `stagger` symbol available to scene code).
- **`render.mjs`** — the entry, aligned to the `/docs/docker` template.

## 4. `render.mjs` contract

Two modes, one file (`node render.mjs <mode> props.json [outdir|out.mp4]`):

1. **Compile step (replaces `new Function`).** For each scene string in `props.json`:
   - prepend the import preamble that supplies the symbols scene code expects as free variables:
     ```ts
     import React from "react";
     import { AbsoluteFill, useCurrentFrame, useVideoConfig, spring,
              interpolate, Sequence, Easing } from "remotion";
     import { Audio } from "@remotion/media";
     import { staticFile } from "remotion";
     import { stagger } from "../../stagger";
     ```
   - apply the same `prepareSource` rename as `compile-check.ts` (export → known symbol);
   - write a **real `.tsx` module** under `src/scenes/`. The bundler (`@remotion/bundler`) transpiles it — no `new Function`.
2. **Assemble the deck with `<Series>`.** `Deck` is the production port of `CombinedComposition` (`combined-player.tsx`): a `<Series>` mapping each slide to `<Series.Sequence durationInFrames={sceneDurations[i]} premountFor={fps}>` containing the scene component + `<Audio src={staticFile(audioFilename)} />`, plus the `Watermark`. `<Series>` chains sequences back-to-back automatically — no manual `from={offset}` bookkeeping (which is what the browser player did). Per-slide `sceneDurations` arrive as resolved props from `calculateMetadata`, so the component never re-measures.
3. **Durations via `calculateMetadata` (exact parity with today's `create_slide_audio`).** For each slide, measure the *actual narration file that will be muxed* with `parseMedia({ src: staticFile(audio), fields: { durationInSeconds: true } })`. `parseMedia` (Mediabunny core) is chosen over `getAudioDurationInSeconds` for two reasons: the latter is **officially deprecated** (docs point to `getMediaMetadata`), and `parseMedia` is **cross-platform (browser + Node + Bun), faster, and format-broader** — so it is robust wherever Remotion evaluates the composition. Then `frames = max(ceil(seconds * fps), min_duration_in_frames)`, reusing the backend's `FPS=30` and 10s (300-frame) floor from `props.json`. Return `{ fps, durationInFrames: Σ frames }` and expose the per-slide `sceneDurations` via `props`. Measuring the bytes that are actually muxed (not a number passed from outside) makes measured and rendered identical, killing sync drift. Slides with no narration fall back to the floor (silent that slide; the MP4 still carries an audio stream from the others).
4. **`--stills props.json outdir/`** — `selectComposition` once, then `renderStill({ composition, serveUrl, output, frame })` per slide, where `frame` is the slide's **cumulative start frame** (the same running offset `<Series>` produces) — not frame 0 each time — so each PNG is a representative keyframe of its slide. Cheap iteration aid.
5. **`props.json out.mp4`** — `bundle()` → `selectComposition({ serveUrl, id: 'Main', inputProps })` (this executes `calculateMetadata`, resolving `fps` + total duration) → `renderMedia({ composition, serveUrl, codec: 'h264', outputLocation: 'out.mp4', inputProps, chromiumOptions: { enableMultiProcessOnLinux: true } })`. Pass the **same `inputProps` to both** `selectComposition` and `renderMedia` (per the official template). Audio is muxed automatically. (`enableMultiProcessOnLinux` is default-on since 4.0.42; kept explicit to mirror the canonical `/docs/docker` template.)

`props.json` shape (written by the backend at runtime, §5). `fps` and `min_duration_in_frames` are passed through from backend config (`VIDEO_PRESENTATION_FPS`, `VIDEO_PRESENTATION_DEFAULT_DURATION_IN_FRAMES`) so timing has **one source of truth** — `calculateMetadata` reads them from here instead of hardcoding `30`/`300`:
```json
{
  "fps": 30,
  "min_duration_in_frames": 300,
  "scenes": [ { "slide_number": 1, "code": "<tsx string>", "audio": "slide-1.mp3" } ]
}
```

## 5. Runtime layout (per render)

The backend copies `/opt/remotion` → a per-render workdir, `write_file`s scene modules + `props.json`, and `write_file`s narration into `<workdir>/public/` (Phase 3) so `staticFile()` resolves. `bundle()` uses the workdir's `public/` as the public dir. Because each video has different generated code, **the bundle is rebuilt per render** (no cross-video reuse) — accepted cost.

## 6. Checks

- In-image fixture: a 2-slide `props.json` (with a short silent WAV in `public/`) →
  - `node render.mjs --stills props.json /tmp/stills` produces 2 PNGs;
  - `node render.mjs props.json /tmp/out.mp4` produces an MP4 that `ffprobe` reports as 1920×1080, duration > 0, with an audio stream.
- A scene string that throws fails the bundle with a captured error on stderr (proves errors surface to the caller, not a silent black frame).

## 7. Exit criteria

1. `docker build` of `docker/sandbox` succeeds with the Remotion layer on the code-interpreter base.
2. Headless Chrome launches inside the sandbox (no missing `.so`).
3. The fixture produces both stills and a playable MP4 with audio, offline.
4. A legacy scene string (old injected-globals contract) bundles unchanged via the preamble — validated on one real sample.
