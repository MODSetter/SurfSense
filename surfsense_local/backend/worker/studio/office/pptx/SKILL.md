---
name: pptx
description: Create polished, editable PowerPoint decks for slide presentations.
---

# PPTX

Author the deck with `python-pptx`, then save it to a `BytesIO`. Plan the slide
purposes and visual system first, then build the whole deck.

## Authoring rules

- Use a 16:9 presentation unless another aspect ratio is asked for. Set
  `prs.slide_width` and `prs.slide_height` once; slide size is deck-wide.
- Use a consistent layout, palette, type scale, spacing, and placement grid
  across the deck.
- Prefer a built-in slide layout and its native placeholders over free-floating
  text boxes. Populate every visible placeholder with final content — never
  leave filler copy or "add image here" notes on a finished slide.
- Keep at least 0.5 inches of outer margin and 0.3 inches between unrelated
  regions. Title and subtitle regions must not overlap.
- Give every slide one clear purpose. Keep body copy concise: normally no more
  than six short bullets, phrases rather than paragraphs.
- Set fonts by family name; default to a common sans like Arial. Use 32–40 pt
  titles, 18–24 pt subtitles, and body text of at least 18 pt. Set
  `text_frame.word_wrap = True`.
- Keep every shape on the slide canvas; do not park unused shapes off-canvas.
- Preserve image aspect ratios: when calling `add_picture`, derive the missing
  dimension from the source rather than stretching both width and height.
- Prefer editable native text, shapes, tables, and charts. Avoid SmartArt and
  elaborate gradients.
