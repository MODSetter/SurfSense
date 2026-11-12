# ADR 0089: Any image model changes a picture: one that takes pictures edits it, any other draws it again

- **Status:** Accepted
- **Date:** 2026-11-10
- **Supersedes:** in part, [ADR 0077](0077-an-image-edit-is-the-next-version.md): its consequence that a picture drawn by a model that cannot edit needs an edit model chosen before it can be edited
- **Source:** maintainer decision, 10 Nov 2026 (no permalink)

## Context

An edit ran only on the `image_edit` selection, which few local models can fill and most users never chose; an empty slot answered "Needs an image editing model" and sent them to Settings. Most remote image models take a picture in, but the image model the user had chosen was never asked. OpenRouter has no `/images/edits`, so an edit through it failed. A comic needs every page to keep page 1's characters, which needs a picture in, not a second model.

## Decision

- Whether a model takes a picture in is a fact about the model, read from its connection's model list or the catalog when it is chosen, not a slot the user fills.
- One rule picks the model for a picture in: the `image_edit` selection when chosen, as an override; else the image model when it takes pictures; else none.
- With none, an edit is drawn again by the image model from the prompt the picture was drawn with and the change, and says so in one plain line. No edit is refused, and nothing in Studio or chat points to Settings for it.
- A picture in goes to `/images/edits`, or to `/images` with `input_references` where a server has no edit route, so OpenRouter edits too.

## Consequences

- Most users choose one image model and edit with it; the edit slot is optional.
- A redraw does not keep the base's composition; the version's first line and the Edit box's placeholder say so.
- Every drawing keeps the prompt it sent, so a redraw has it, and changes add up from version to version.
