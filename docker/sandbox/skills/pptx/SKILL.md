---
name: pptx
description: Create polished, editable PowerPoint files for slide decks, presentations, and explicit .pptx requests.
---

# PPTX

Create the requested presentation in `/workspace` with the preinstalled
`python-pptx` package. Never install or download dependencies.

Use one deliverable-derived stem for deterministic Python source and output, for
example `quarterly-review.py` and `quarterly-review.pptx`. The source must
regenerate the complete deck so later revisions edit rather than reconstruct it.

## Authoring rules

- Use a 16:9 presentation unless the user requests another aspect ratio. Set
  `prs.slide_width` and `prs.slide_height` once; slide size is deck-wide.
- Use a consistent layout, palette, type scale, spacing system, and placement
  grid across the deck. Prefer the default template's layouts and placeholders
  over unrelated free-positioned text boxes.
- Give every slide one clear purpose. Keep body copy concise: normally no more
  than six bullets, with short phrases rather than paragraphs.
- Set font sizes explicitly and keep body text at least 18 pt. Set
  `text_frame.word_wrap = True`. Do not rely on autofit: PowerPoint and
  LibreOffice lay it out differently, and the verified preview uses LibreOffice.
- Keep every shape on the slide canvas. Intentional edge bleed may cross a slide
  boundary, but do not park unused shapes off-canvas or hide backup slides.
- Preserve image aspect ratios. When calling `add_picture`, derive the missing
  dimension from the source image instead of setting both width and height to
  unrelated values. Crop deliberately and keep crop values within 0–100%.
- Prefer editable native text, shapes, tables, and charts. Avoid SmartArt and
  elaborate gradients whose LibreOffice conversion is unreliable.

Build slides incrementally in the Python source and leave local assertions for
slide count, shape bounds, and required content. Generate the complete PPTX
before verification; do not call `verify_artifact` after each slide because each
call renders and reviews the whole draft again.

When revising, `load_artifact_source` returns the existing `document_id` and a
`source_path` with a name such as `artifact-42-quarterly-review.py`. Copy that
source to `quarterly-review.py` before editing so the `artifact-42-` prefix does
not compound, then pass the returned `document_id` to `save_artifact`. A changed
title, filename, or design is still the same artifact unless the user explicitly
asks for a separate copy.

## Verify and save

Call `verify_artifact(path="quarterly-review.pptx")`. Warnings are advisory. If
it reports blocking findings, fix them in the Python source, regenerate once,
and reverify. If a blocker remains, stop and explain it rather than entering
another automatic rewrite loop.

Then call `save_artifact` with the PPTX path, Python source path, and the exact
`preview_path` returned by verification. The Markdown representation must
faithfully contain the deck's substantive text for accessibility and search.
