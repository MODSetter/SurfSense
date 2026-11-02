# ADR 0077: An image edit is the next version of the same document

- **Status:** Accepted
- **Date:** 2026-10-31
- **Supersedes:** the removal of Studio's earlier image Edit, which made a new artifact per edit
- **Source:** maintainer decision, 31 Oct 2026 (no permalink)

## Context

The `image_edit` slot could be filled in Settings and onboarding, and FLUX.2 klein 4B filled it, but nothing read it ([selection](../architecture/local-models/selection.md)). A Studio Edit that made a new artifact per edit was built and taken out, because whether an edit replaces an image or makes a new one was not decided. Word documents, PDFs and web pages already have Refine: each rewrite is the next version of one document, under `version` keys in `artifact_metadata`, with a version switcher ([studio](../architecture/studio.md#refine)).

## Decision

- An edit of a Studio image or infographic is the next version of the same document, under the keys a refine writes. A drawn picture is v1 with `recipe: drafted()`.
- The recipe names the base version, `{"kind": "image_edit", "instruction", "base_artifact_id"}`, and the edit reads that version's own file, so edits chain.
- Regenerate on an edit repeats the edit on the same base; on a draft it still draws from the sources.
- The instruction goes to the edit model as written, with no chat model rewriting it first, and an edit is not retried.
- An edit has its own slice and route, `POST /artifacts/{id}/image-edit`, and shares Refine's box in the interface.
- Locally, an edit posts sd-server's native `img_gen` with the picture as a reference image only, because its OpenAI and A1111 edit routes also make it the starting noise and re-draw it.

## Consequences

- Images and documents share one version model, so the list, the switcher and deletion need nothing new. The `artifact_versions` table the file agent design plans replaces the keys for every format at once.
- An edit costs one call to the edit model and no chat model, so it starts without waiting for the chat model to load.
- An infographic's brief no longer matches its picture exactly after an edit; its body records each instruction instead.
- A model that only re-noises a picture cannot be chosen to edit, so an image drawn by SDXL needs an edit model chosen too before it can be edited.
