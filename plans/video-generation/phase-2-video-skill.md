# Phase 2 — The `video` skill + agent wiring

**Status:** DESIGN.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Depends on:** Phase 1 (harness in the image); the deliverables sub-agent (`app/agents/chat/multi_agent_chat/subagents/builtins/deliverables/`).

## 1. Goal

The deliverables agent authors a video the same way it authors a PDF: load the skill, `execute` render code in the sandbox, self-review stills, iterate, then `verify_artifact` → `save_artifact`. No dedicated video tool.

## 2. The skill — `docker/sandbox/skills/video/SKILL.md`

A trusted instruction file (baked into `/opt/skills/video/` by the existing skills copy in `docker/sandbox/Dockerfile`). It encodes taste + the loop, mirroring `docker/sandbox/skills/{pdf,pptx}/SKILL.md`:

- **Composition rules:** 1920×1080 @ fps 30; safe outer margins; body contrast; motion timing/easing; one purpose per slide; keep shapes on-canvas; the SurfSense watermark is supplied by the harness (do not re-add).
- **Authoring contract:** write each slide as a Remotion component; imports from the baked `node_modules` are allowed (real bundler). The harness supplies `stagger` and standard `remotion` symbols via the preamble.
- **Narration:** call `synthesize_narration` (Phase 3) for the slide transcripts; it writes audio into the render workdir's `public/` and returns filenames. Reference them in `props.json`; do not fetch audio yourself (no network).
- **The loop:**
  1. author scenes + `props.json`;
  2. `execute` `node render.mjs --stills props.json /tmp/stills` and review the PNGs (`read_sandbox_file` is text-only, so review via the verify/vision path or re-render);
  3. fix and re-run stills until they pass the skill's checklist;
  4. `execute` the full render → `/workspace/out.mp4`;
  5. `verify_artifact(path="/workspace/out.mp4")`;
  6. `save_artifact(path=..., title=..., markdown_representation=...)` — the markdown must faithfully carry the deck's substantive text for search/accessibility.
- **Constraints:** never `npm install` / download (everything baked); a single render must fit `SANDBOX_OPERATION_TIMEOUT_SECONDS` — for long decks, render in segments and `ffmpeg concat`.

## 3. Wiring

- **`deliverables/tools/sandbox.py`** — extend `load_artifact_instructions`'s `Literal["pdf","docx","pptx","xlsx"]` to include `"video"` so it `cat`s `/opt/skills/video/SKILL.md`.
- **`deliverables/system_prompt.md`** — route "make a video / presentation / narrated deck" into the skill workflow, exactly as documents are routed. Remove any language that points at the old `generate_video_presentation` tool (its removal is Phase 7).
- **No new tool registration** for authoring — `execute`, `verify_artifact`, `save_artifact` already exist in `tools/index.py`.

## 4. Language guarantee (unchanged)

Rendering runs through `execute(language="bash")` invoking `node render.mjs`. The `execute` schema stays `Literal["python","bash"]`; JS/TS is authored as files and run via Node under bash. No new language surface is exposed.

## 5. Checks

- Unit: `load_artifact_instructions("video")` returns the skill body (mirror the existing skill-load contract test).
- Agent test: a "make a video" request drives `load_artifact_instructions("video")` → `execute` (stills) → `execute` (mp4) → `verify_artifact` → `save_artifact`, with no Celery dispatch and no `generate_video_presentation` call.

## 6. Exit criteria

1. The video skill is present in the image and loadable by the agent.
2. The deliverables prompt routes video work to the skill loop.
3. A model run produces `/workspace/out.mp4` using only `execute` + the baked harness.
