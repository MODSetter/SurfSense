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
# system ffmpeg/ffprobe used for: segment concat of long decks (Phase 2 §5),
# the in-sandbox structural probe, and the single-frame content-sanity sample
# (Phase 4). Remotion's own bundled ffmpeg handles render/mux (§3); these are the
# steps that shell out to ffmpeg/ffprobe directly, so we add the binaries on PATH.
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
- `ffprobe` ships **with** the `ffmpeg` package installed above, so the trusted-side verify (Phase 4) and the in-sandbox structural probe need no extra layer.

## 2a. Baked font palette (offline — the jail has no network)

The jail is `NetworkPolicy(default_action="deny")`, so any web font the model references (`@remotion/google-fonts`, a bare `@font-face url()`) **silently fails and Chrome falls back** — producing a structurally-valid MP4 that looks wrong, which structural verify (Phase 4) cannot catch. So the harness ships a **fixed, closed set of three families**, installed as *system* fonts (fontconfig) so scene code uses them by `fontFamily` name with no `loadFont` wiring:

```dockerfile
# ---- Baked fonts: the ONLY families scene code may use (offline) ----
# Vendored .ttf under docker/sandbox/remotion/fonts/ (Inter, Lora, JetBrains Mono),
# installed system-wide so headless Chrome resolves them by family name.
COPY remotion/fonts/ /usr/share/fonts/truetype/surfsense/
RUN fc-cache -f && fc-list | grep -Ei 'inter|lora|jetbrains' >/dev/null
```

The three families are a deliberate, versatile trio — **do not expand without also vendoring the file** (an unlisted family will fall back, not error):

| Role | Family | Use |
|---|---|---|
| Sans (default) | **Inter** | body copy, most headings, UI-style slides |
| Serif | **Lora** | editorial/quote/title contrast |
| Mono | **JetBrains Mono** | code, figures, data labels, tabular numerals |

The `fc-list` grep is the build-time assertion: a font that didn't install fails `docker build` rather than falling back at render. Vendoring the `.ttf` bytes (not an apt package) keeps the set reproducible across base-image changes and free of network at build.

## 3. New harness — `docker/sandbox/remotion/`

Baked at build time (scaffolding + deps only; scenes/audio are injected at runtime):

- **`package.json`** — `remotion`, `react`, `react-dom`, `@remotion/bundler`, `@remotion/renderer`, `@remotion/media` (the modern, Mediabunny-backed `<Audio>` — the recommended tag for new projects, not the legacy core `remotion` `<Audio>`), `@remotion/media-parser` (`parseMedia`, the non-deprecated successor to `getAudioDurationInSeconds`, used for duration probing in §4). FFmpeg ships inside `@remotion/renderer` for the render/mux step, so no apt ffmpeg is needed *for rendering* — but a system `ffmpeg`/`ffprobe` is still installed in §2 for the steps that shell out directly: **segment concat** for long decks (Phase 2 §5), the **in-sandbox structural probe**, and the **single-frame content-sanity sample** (Phase 4). None of these go through the renderer. Verify uses no *vision LLM* and no *per-frame* extraction — just one sampled frame for a local histogram.
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
5. **`props.json out.mp4`** — `bundle()` → `selectComposition({ serveUrl, id: 'Main', inputProps })` (this executes `calculateMetadata`, resolving `fps` + total duration) → `renderMedia({ composition, serveUrl, codec: 'h264', outputLocation: 'out.mp4', inputProps, chromiumOptions: { enableMultiProcessOnLinux: true }, timeoutInMilliseconds: RENDER_FRAME_TIMEOUT_MS })`. Pass the **same `inputProps` to both** `selectComposition` and `renderMedia` (per the official template). Audio is muxed automatically. (`enableMultiProcessOnLinux` is default-on since 4.0.42; kept explicit to mirror the canonical `/docs/docker` template.)
   - **Bound a pathological frame.** `timeoutInMilliseconds` caps per-frame work (the `delayRender()` budget). Model code executes in Chrome during render, so a scene with an unresolved `delayRender()`, a `fetch` that hangs on the denied network, or a runaway loop would otherwise pin the sandbox slot for the entire `SANDBOX_OPERATION_TIMEOUT_SECONDS` and starve the admission gate (Phase 2 §5). Set `RENDER_FRAME_TIMEOUT_MS` **well below** that per-`execute` budget (default Remotion is 30 000 ms; tighten to a few seconds) so a bad frame throws a captured error fast instead of eating the whole render. `--stills` (§4.4) takes the same `timeoutInMilliseconds`.

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

**Clean the workdir in a `finally`.** Each render's workdir (copied harness + injected scenes/audio + the bundle output + `out.mp4`) is deleted after the MP4 is read back — success or failure — mirroring `verification/render.py::cleanup_render_files`. Segment renders for long decks (Phase 2 §5) and backfill batches (Phase 7) run many renders through one long-lived session, so without cleanup the sandbox disk fills. Cleanup must never mask the render verdict (best-effort `rm -rf`, swallow its own error).

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
