---
name: html
description: Create interactive calculators, configurators, dashboards, widgets, and prototypes as self-contained HTML artifacts.
---

# Interactive HTML

Create one interactive HTML fragment in `/workspace`. Everything required is
available in the browser; never install or download dependencies.

## Authoring contract

- Emit a fragment only. Do not include `<!DOCTYPE>`, `<html>`, `<head>`, or
  `<body>`; the artifact viewer supplies the document shell and security policy.
- Put all CSS in `<style>` and all behavior in inline `<script>`.
- Keep state in memory. The sandboxed viewer does not provide application APIs,
  cookies, or durable browser storage.
- Do not call `fetch`, XMLHttpRequest, WebSocket, or application APIs.
- Images must be `data:` URIs. The only external resources the viewer permits
  are stylesheets and fonts from `fonts.googleapis.com` and
  `fonts.gstatic.com`.
- Use semantic HTML and native controls. Every input needs an accessible label,
  keyboard focus must be visible, and motion must respect
  `prefers-reduced-motion`.
- Make the layout responsive without horizontal page overflow.

## Web design requirements

- Design mobile-first and verify narrow and wide layouts without horizontal
  overflow.
- Use one `h1`, ordered heading levels, native controls, and explicit labels.
- Keep CSS selectors local and simple to avoid specificity conflicts.
- Make touch targets usable and provide `:focus-visible` styles.
- Respect `prefers-reduced-motion`; do not animate every section or card.

## Revisions

Start an in-place revision with `load_artifact_for_revision`. Edit
`primary_path` directly, or regenerate the fragment from `markdown_path` plus
the user's instruction, and write it to `expected_output_path`. Keep the
output a self-contained fragment. Do not use vision to reconstruct the current
page.

Save the verified revision with the returned `artifact_id` and
`expected_generation`. A changed title or design remains the same artifact
unless the user explicitly asks for a separate copy.

## Verify and save

Call `verify_artifact(path=output_path, format="html")`. HTML verification is structural only:
there is no PDF preview or vision pass. Warnings identify resources the viewer
will block and do not require regeneration. If verification reports blocking
findings, fix all blockers together, regenerate once at the same output path,
and reverify. If a blocker remains, stop and explain it instead of looping.

Then call `save_artifact(path=output_path, title="...",
markdown_representation="...")`. Working files may use any paths; no source
file, preview file, or matching filename stem is part of the publication
contract.

The Markdown representation must faithfully summarize the artifact's purpose,
controls, outputs, and important content for accessibility and search. Do not
paste the raw HTML into it.
