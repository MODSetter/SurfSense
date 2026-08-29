---
name: video
description: Create polished narrated MP4 videos with Remotion in the sandbox.
---

# Video

Create one narrated 1920×1080 MP4 at 30 fps in `/workspace`. Use the baked
`/opt/remotion` harness and dependencies. Never install or download anything.
The sandbox has no network.

## Plan before rendering

Draft the complete deck specification first. For every slide include its
on-screen text and narration line. Keep this specification unchanged: pass its
narration lines to `synthesize_narration`, and later use the full specification
as `markdown_representation`. It is the durable accessible and editable source;
scene files and `props.json` are ephemeral.

Refuse requests above the 12-scene product limit rather than silently
shortening them. The selected composition must also be at most 180 seconds.

## Composition rules

- Give each slide one clear purpose. Keep safe outer margins, readable body
  contrast, restrained motion, and every shape on the 1920×1080 canvas.
- The harness supplies sequencing, narration audio, and the SurfSense
  watermark. Do not add another watermark or audio element.
- Use only these system-installed font families: `Inter` for normal text,
  `Lora` for editorial titles or quotes, and `JetBrains Mono` for code and
  figures. No other family is available reliably offline. Do not use
  `loadFont`, `@font-face`, or `@remotion/google-fonts`.
- Write one complete, self-contained TSX module per slide. Each module must
  import every dependency it uses and have a default component export. The
  harness writes the module verbatim: it does not inject globals, strip imports,
  or rewrite exports. Dependencies must already exist in baked `node_modules`.

Use this exact module shape:

```tsx
import type React from "react";
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from "remotion";
import {stagger} from "../../stagger";

const Scene: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const entrance = stagger(frame, fps, 0, 1);

  return (
    <AbsoluteFill
      style={{
        alignItems: "center",
        backgroundColor: "#101828",
        color: "white",
        fontFamily: "Inter",
        justifyContent: "center",
      }}
    >
      <h1 style={{fontSize: 96, ...entrance}}>A clear opening</h1>
    </AbsoluteFill>
  );
};

export default Scene;
```

There are no assumed `React`, `AbsoluteFill`, `useCurrentFrame`,
`useVideoConfig`, `interpolate`, `spring`, `staticFile`, `Audio`, or `stagger`
globals. Import only what that scene uses.

## Build loop

1. Copy `/opt/remotion` to a fresh per-render work directory.
2. Call `synthesize_narration` once with every `{slide_number, transcript}` and
   that work directory. It writes files under `public/` and returns filenames.
   Never fetch audio yourself.
3. Write `props.json` with `fps`, `min_duration_in_frames`, and ordered
   `{slide_number, code, audio}` scenes. Use returned audio filenames exactly.
4. Run `node render.mjs --preflight props.json`. It validates input, writes the
   verbatim modules, bundles them, selects the composition, and enforces the
   180-second limit without rendering frames.
5. Run `node render.mjs --stills props.json /tmp/stills`. Inspect each scene's
   start, middle, and end PNG plus `contact-sheet.png` for clipping, overflow,
   contrast, hierarchy, blank frames, and safe margins.
6. If preflight or still review fails, make one coordinated repair and repeat
   preflight and still review once. If it still fails, stop; do not keep
   repairing.
7. Run the full `node render.mjs props.json /workspace/out.mp4`. The harness
   measures narration with `parseMedia`, derives timing, segments long renders,
   and concatenates them. Do not hand-calculate audio frame counts.
8. Call `verify_artifact(path="/workspace/out.mp4")`. If it reports a blocking
   finding, make one final repair, then run preflight, still review, render, and
   verification once more. A second verification failure is terminal.
9. Call `save_artifact` only after the exact MP4 verifies, passing the step-1
   deck specification as `markdown_representation`.

The workflow permits at most two repairs total: one compile/still repair and
one final verification repair.

A render must fit the sandbox operation timeout. The harness controls segment
size; do not bypass it. A successful save removes the render work directory;
if rendering or verification fails terminally, remove that directory before
reporting the failure. For revisions, regenerate from the restored Markdown
specification plus the user's instruction, then render and verify a new MP4.
Do not edit `current.mp4` in place.
