# alert-dialog

2026-09-25, golden pair, plus a wrapper-level fix for Action.

## Changed

- `src/components/ui/alert-dialog.tsx`: `Overlay` → `Backdrop`, `Content` → `Popup`, `Cancel` → `Close` with `render={<Button/>}`.
- `AlertDialogAction`: base-nova makes it a plain `Button`, which does **not** close the dialog. Five callers relied on Radix closing it (flashcards reset, connection disconnect, try-model unlisted, artifact delete, sources delete); two block the close with `event.preventDefault()` (egress prompt, delete model). The wrapper now renders `AlertDialogPrimitive.Close` and maps `preventDefault()` to `event.preventBaseUIHandler()`. Callers are unchanged, and both behaviours keep working.
- `disconnect-button.tsx`, `flashcards-viewer.tsx`: `AlertDialogTrigger asChild` → `render`.
- Leftover scan clean: `grep -n "radix-ui\|@radix-ui"` finds nothing in this component's files.

## Left alone

- Nothing related.

## Behavior changes

- None intended: Action keeps Radix's close-unless-prevented contract (a deliberate departure from base-nova, noted in the wrapper).

## Verify by hand

- Delete a source, confirm: the dialog closes and the row goes.
- Models → delete a model: while it deletes, the dialog stays open with a spinner.
- Egress prompt → Allow: stays open while allowing.
- Cancel and Esc both close and return focus to the trigger.
