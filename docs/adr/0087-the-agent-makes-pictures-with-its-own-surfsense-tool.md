# ADR 0087: The agent makes pictures with its own SurfSense tool, not opencode's

- **Status:** Accepted; its waiting for the user's next message superseded by [ADR 0090](0090-a-document-waits-on-the-server-for-its-pictures.md)
- **Date:** 2026-11-07
- **Amends:** [ADR 0066](0066-web-pages-are-html-the-model-writes-without-network.md), in part: its rule that nothing is written into a page but the policy
- **Source:** maintainer decision, 7 Nov 2026 (no permalink)

## Context

The agent could start Studio's image job only from ticked sources, with a chat model rewriting its request, and got nothing back to look at or place. Documents could place only source figures and analysis charts.

opencode 2.2 added `experimental_image_generate`. A spike on 2.2.5 with SurfSense's configuration found it writes files and edits through `/images/generations` and `/images/edits`, but runs in the background: the turn goes idle before the picture is ready, and a second run brings the notice. It is listed only when a provider has an image model.

## Decision

- The agent draws through `surfsense_make_image`, a SurfSense tool over Studio's job, not opencode's tool.
- A picture is a normal Studio artifact, with versions, the viewer and the Edit box, and needs only an image model: the agent writes the prompt, and no chat model rewrites it.
- `image-<artifact id>` names one version, and only the chat that made it can place or edit it.
- A tool call keeps its limit. A picture past it answers as queued, and no tool polls.
- A page names an image as `surfsense-image:<name>`, and saving makes it a `data:` URL. The agent has no shell, and typing base64 through a model is not practical.

## Consequences

- opencode threads and Claude plan threads get the same tool, which opencode's would not reach. The pinned opencode stays at 2.1.2, with no new model routes or second-run handling.
- Local pictures run through the existing sd-server and text-runtime hold.
- A stored page is what the model wrote, its images inline, plus the policy. Its working file keeps the names.
- A document needing a picture still being drawn waits for the user's next message.
- Studio's own buttons keep drafting from sources through a chat model, and Studio's drafts cannot place these pictures.
