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
- Keep at least 0.5 inches of outer margin and 0.3 inches between unrelated
  content regions. Define title, subtitle, body, and footer regions once and
  reuse them; title and subtitle regions must not overlap.
- Give every slide one clear purpose. Keep body copy concise: normally no more
  than six bullets, with short phrases rather than paragraphs.
- Default to Arial for fit-sensitive text; LibreOffice substitutes the
  metric-compatible Liberation Sans installed in the sandbox. Use Times New
  Roman/Liberation Serif when a serif is appropriate, and Noto for scripts they
  do not cover. If the user requires another font, leave about 10% extra width
  and height because LibreOffice and PowerPoint may use different metrics.
- Use 32–40 pt titles, 18–24 pt subtitles, and body text of at least 18 pt. Set
  `text_frame.word_wrap = True` and explicit text-frame margins; use zero
  margins where text must align exactly with a nearby shape.
- Do not use PowerPoint runtime autofit (`text_frame.auto_size`) because
  PowerPoint and LibreOffice can resolve it differently. For a single-style
  title or subtitle, use `text_frame.fit_text(...)` with an explicit Liberation
  font file so the fitted size is written into the PPTX. If a title must shrink
  below 28 pt or a subtitle below 16 pt, shorten it, enlarge its region, or
  split the content across slides instead of accepting the smaller text.
- Keep every shape on the slide canvas. Intentional edge bleed may cross a slide
  boundary, but do not park unused shapes off-canvas or hide backup slides.
- Preserve image aspect ratios. When calling `add_picture`, derive the missing
  dimension from the source image instead of setting both width and height to
  unrelated values. Extended crop values are legal, but the left and right crop
  fractions must sum to less than 1, as must the top and bottom fractions, so
  some of the image remains visible.
- Prefer editable native text, shapes, tables, and charts. Avoid SmartArt and
  elaborate gradients whose LibreOffice conversion is unreliable.

Build slides incrementally in the Python source. Before saving the PPTX, run
local assertions that name the slide and shape when they fail:

- required slide count and content are present;
- title and subtitle regions do not overlap;
- area shapes have positive width and height, while a connector may have one
  zero extent but not two;
- every shape intersects the slide canvas; and
- fitted title and subtitle text remains above the minimum sizes above.

Generate the complete PPTX and pass those local checks before verification. Do
not call `verify_artifact` after each slide because each call renders and reviews
the whole draft again.

When revising, `load_artifact_source` returns the existing `document_id` and a
`source_path` with a name such as `artifact-42-quarterly-review.py`. Copy that
source to `quarterly-review.py` before editing so the `artifact-42-` prefix does
not compound, then pass the returned `document_id` to `save_artifact`. A changed
title, filename, or design is still the same artifact unless the user explicitly
asks for a separate copy.

## Verify and save

Call `verify_artifact(path="quarterly-review.pptx")`. Warnings are advisory. If
it reports blocking findings, fix all reported blockers together in the Python
source, rerun the local checks, regenerate once, and reverify. If a blocker
remains, stop and explain it rather than entering another automatic rewrite
loop.

Call `save_artifact` only when the latest verification of those exact PPTX bytes
returned `status="verified"`. Use the Python source path and exact `preview_path`
from that result. A failed verification invalidates every earlier pass: never
attempt to save afterward. The Markdown representation must faithfully contain
the deck's substantive text for accessibility and search.
