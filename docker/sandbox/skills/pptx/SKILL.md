---
name: pptx
description: Create polished, editable PowerPoint files for slide decks, presentations, and explicit .pptx requests.
---

# PPTX

Create an editable `.pptx` in `/workspace` with the preinstalled `python-pptx`
package. Never install or download dependencies. For a new deck, set
`output_path` to a descriptive `/workspace/<name>.pptx` path.

Use this order:

1. Plan the slide purposes and visual system.
2. Build the complete deck.
3. Run the local checks below.
4. Verify the complete deck once.
5. If verification fails, repair it once and reverify.
6. Save the artifact only after the latest verification passes.

## Authoring rules

- Use a 16:9 presentation unless the user requests another aspect ratio. Set
  `prs.slide_width` and `prs.slide_height` once; slide size is deck-wide.
- Use a consistent layout, palette, type scale, spacing system, and placement
  grid across the deck.
- Prefer a suitable built-in PowerPoint layout and its native placeholders over
  unrelated free-positioned text boxes. A native placeholder is a layout
  container, not permission to leave filler copy visible: populate every
  visible placeholder with final content unless the user explicitly requests a
  reusable template.
- Treat requests for "image placeholders", "visual suggestions", or "design
  concepts" as design direction for a finished deck. Add the real visual or a
  finished graphic treatment; do not display those instructions as slide text.
- Keep at least 0.5 inches of outer margin and 0.3 inches between unrelated
  content regions. Define title, subtitle, body, and footer regions once and
  reuse them; title and subtitle regions must not overlap.
- Give every slide one clear purpose. Keep body copy concise: normally no more
  than six bullets, with short phrases rather than paragraphs.
- Set fonts in the deck by family name. Default to Arial for fit-sensitive
  text; LibreOffice substitutes the metric-compatible Liberation Sans installed
  in the sandbox. Use Times New Roman/Liberation Serif when a serif is
  appropriate, and Noto for scripts they do not cover. If the user requires
  another font, leave about 10% extra width and height because LibreOffice and
  PowerPoint may use different metrics.
- Never guess or hardcode a font-file path. A path is needed only when calling
  `text_frame.fit_text(...)`; resolve it at runtime with `fc-match`, for example
  `fc-match -f '%{file}\n' Arial`, and use the first non-empty line. If no file
  is returned, do not call `fit_text`; shorten the text or enlarge its region.
- Use 32–40 pt titles, 18–24 pt subtitles, and body text of at least 18 pt. Set
  `text_frame.word_wrap = True` and explicit text-frame margins; use zero
  margins where text must align exactly with a nearby shape.
- Do not use PowerPoint runtime autofit (`text_frame.auto_size`) because
  PowerPoint and LibreOffice can resolve it differently. For a single-style
  title or subtitle, `text_frame.fit_text(...)` may be used with the font file
  resolved above so the fitted size is written into the PPTX. If a title must
  shrink below 28 pt or a subtitle below 16 pt, shorten it, enlarge its region,
  or split the content across slides instead.
- Keep every shape on the slide canvas. Intentional edge bleed may cross a slide
  boundary, but do not park unused shapes off-canvas or hide backup slides.
- Preserve image aspect ratios. When calling `add_picture`, derive the missing
  dimension from the source image instead of setting both width and height to
  unrelated values. Extended crop values are legal, but the left and right crop
  fractions must sum to less than 1, as must the top and bottom fractions, so
  some of the image remains visible.
- Prefer editable native text, shapes, tables, and charts. Avoid SmartArt and
  elaborate gradients whose LibreOffice conversion is unreliable.

## Local validation

Before verification, run local assertions against the complete deck. Every
failure must name the slide and shape so it can be repaired directly:

- required slide count and content are present;
- title and subtitle regions do not overlap;
- area shapes have positive width and height, while a connector may have one
  zero extent but not two;
- every shape intersects the slide canvas; and
- fitted title and subtitle text remains above the minimum sizes above;
- no visible TODOs, editor notes, design suggestions, or replacement
  placeholders remain in a finished deck.

Save the PPTX to `output_path`, reopen it with `python-pptx`, and confirm the
slide count and required content. Do not call `verify_artifact` after each slide;
verification renders and reviews the whole deck.

## Revisions

Start an in-place revision with `load_artifact_for_revision`. Open
`primary_path` with `python-pptx`, edit that current deck directly, and save the
result to `expected_output_path`; for the revision, that path is `output_path`.
Preserve unaffected slide masters, layouts, notes, relationships, and media.
Use `markdown_path` as textual context, not as a replacement deck. Do not
reconstruct slides with vision; `verify_artifact` may use vision after the
revision is written.

A changed title, filename, or design is still the same artifact unless the user
explicitly asks for a separate copy. After verification, save the revision with
the returned `artifact_id` and `expected_generation`.

## Verify and save

1. Call `verify_artifact(path=output_path, format="pptx")` once after local
   validation.
2. If it returns blocking findings, fix all of them together. Repair the exact
   offending shapes in place: update, resize, or delete obsolete elements before
   adding replacements. Never cover an old element with a new one.
3. Rerun the local checks, overwrite the same `output_path`, and call
   `verify_artifact` once more. Warnings are advisory.
4. If any blocker remains, stop and explain it. Do not enter another automatic
   rewrite loop.

Call `save_artifact` only when the latest verification of those exact PPTX bytes
returned `status="verified"`, using
`save_artifact(path=output_path, title="...", markdown_representation="...")`.
A failed verification invalidates every earlier pass: never attempt to save
afterward. Working files may use any paths; no source file, preview file, or
matching filename stem is part of the publication contract. The Markdown
representation must faithfully contain the deck's substantive text for
accessibility and search.
