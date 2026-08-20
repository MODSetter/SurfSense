# Phase 3 — Trusted-side narration bridge

**Status:** DESIGN.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Depends on:** Phase 1 (harness `public/` convention). Reuses TTS logic from `app/agents/video_presentation/nodes.py::create_slide_audio`.

## 1. Goal

Narration audio (TTS needs network) reaches the sandbox **without** giving the jail network — the trusted side generates it and writes the bytes into the render workdir's `public/`.

## 2. New tool — `deliverables/tools/synthesize_narration.py`

A trusted, network-using deliverables tool (same class as `generate_image`/`podcast`):

- **Input:** `[{ slide_number, transcript }]` and the render workdir (or resolves the session like `_get_session`).
- **Behavior:** lift the existing per-slide TTS from `video_presentation/nodes.py::create_slide_audio` (voice resolution, provider call, billing hooks). For each slide, synthesize audio and `session.write_file` it to `<workdir>/public/slide-<n>.<ext>`.
- **Output:** `[{ slide_number, audio: "slide-<n>.<ext>" }]` — **filenames only**, so the model references them via `staticFile()` in `props.json`. Durations are derived in-sandbox from the file by `calculateMetadata` (`parseMedia`, Phase 1 §4.3), so the tool need not report frame counts.
- Register in `deliverables/tools/index.py::load_tools` alongside the other trusted media tools.

## 3. Trust boundary

The TTS call and credentials live on the trusted side. Only inert audio **bytes** cross into the sandbox via `session.write_file` into `public/`. The jail still has no network — it receives audio files to stitch, exactly as it receives scene code.

## 4. Notes / risks

- **Billing:** reuse the existing video-presentation billing hooks so narration cost accounting does not regress.
- **Placement law:** audio must land in `public/` (not arbitrary paths) or `staticFile()` will not resolve at bundle time.
- **Language/voice:** carry over the language handling from the current graph (`PresentationSlides.language`).

## 5. Checks

- Unit: given N transcripts and a fake session, the tool writes N files under `public/` and returns matching `{slide_number, audio}` filenames.
- Integration (mock TTS): filenames returned resolve to non-empty files that `parseMedia` can measure a positive `durationInSeconds` from.

## 6. Exit criteria

1. The agent can obtain narration for a deck via one trusted tool call.
2. Audio lands in the workdir `public/`, referenced by filename.
3. The sandbox never gains network to produce narration.
