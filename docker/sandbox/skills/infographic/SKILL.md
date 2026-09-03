---
name: infographic
description: Create a factual, image-model-generated infographic through the unified artifact workflow.
---

# Infographics

The user has already selected a trusted visual-style preset. Use the
`infographic_selection_token` returned with these instructions exactly as
provided. Do not call `generate_image`, invent a style, or rewrite the selected
style.

## Author the factual contract

Create concise canonical Markdown in memory:

- Start with one H1 title and a short summary.
- Add ordered H2 sections with every exact visible label, number, unit,
  relationship, and source context the image must preserve.
- Keep visible copy short. Prefer labels, short sentences, and explicit
  relationships over paragraphs.
- Do not invent claims. Resolve conflicting or unsupported facts before
  generation.
- Honor an explicit audience and aspect ratio; otherwise use a broadly readable
  general-audience layout.

## Generate

Call the existing `execute` tool once with:

```text
execute(
  language="infographic",
  code_or_command="<exact canonical Markdown>",
  infographic_selection_token="<trusted token>",
  output_path="/workspace/<slug>.png",
  output_constraints="<audience/aspect ratio when applicable>"
)
```

The backend invokes the configured image model, normalizes one bounded PNG, and
writes the exact Markdown companion at `/workspace/<slug>.md`. Do not edit the
PNG or Markdown after generation.

## Verify, repair once, and save

Call:

```text
verify_artifact(
  path="/workspace/<slug>.png",
  format="infographic",
  markdown_path="/workspace/<slug>.md"
)
```

If verification fails, pass all findings together to exactly one more
`execute(language="infographic", repair_findings=[...])` call with the same
Markdown, token, and output path, then verify again. If any blocker remains,
stop and explain it. Do not loop or save.

After verification returns `status="verified"`, call:

```text
save_artifact(
  path="/workspace/<slug>.png",
  title="...",
  markdown_representation="<exact contents of /workspace/<slug>.md>"
)
```

Only `save_artifact` makes the infographic durable. Sandbox files and provider
URLs are transient.
