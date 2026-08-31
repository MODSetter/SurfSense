---
name: mindmap
description: Create concise hierarchical mind maps as canonical Markdown with a static PNG download.
---

# Mind maps

Author the hierarchy as Markdown; do not author CSS, colors, HTML, SVG, renderer
options, or a separate visual design. Markmap's built-in stylesheet and default
options own the appearance.

## Content contract

Create `/workspace/<slug>.md` with exactly one non-empty level-one heading and
a nested unordered list beneath it. Use two spaces per nesting level.

- Include 2–6 balanced top-level branches where the subject supports them.
- Keep labels short and specific; do not put paragraphs in nodes.
- Maximums include the root: 60 nodes, depth 6, 120 characters per label.
- Do not skip nesting levels or use empty labels.
- Do not use raw HTML, images, links, fenced code, tables, directives, remote
  assets, or control characters.
- Inline emphasis and inline code are acceptable.

## Render

Run the baked renderer; do not install packages, another browser, `markmap-cli`,
or any network dependency:

```bash
node /opt/remotion/render-mindmap.mjs \
  /workspace/<slug>.md \
  /workspace/<slug>.png
```

The command validates the bounded hierarchy, expands every branch, fits the
map, and atomically writes an exact 2400×1600 PNG. If it reports that the map is
too dense, simplify or split the hierarchy instead of changing styles or
renderer options.

## Verify and save

Call:

```text
verify_artifact(
  path="/workspace/<slug>.png",
  format="mindmap",
  markdown_path="/workspace/<slug>.md"
)
```

Fix all blocking findings together, rerender once, and reverify both exact
paths. If a blocker remains, stop and explain it instead of looping.

After verification returns `status="verified"`, call:

```text
save_artifact(
  path="/workspace/<slug>.png",
  title="...",
  markdown_representation="<exact contents of /workspace/<slug>.md>"
)
```

The Markdown argument must be byte-for-byte the verified source; do not
summarize it. For revisions, edit the returned `markdown_path`, render to
`expected_output_path`, verify both paths together, and save with the returned
`artifact_id` and `expected_generation`. Never edit or reconstruct the PNG.
