# button-group

2026-09-25, golden pair. `Slot` → `useRender` + `mergeProps` for `ButtonGroupText`.

## Changed

- `src/components/ui/button-group.tsx`: local `<fieldset>` root kept; `ButtonGroupText` now uses `useRender` (gains `data-slot="button-group-text"`).
- Leftover scan clean: `grep -n "radix-ui\|@radix-ui"` finds nothing in this component's files.

## Left alone

- `thread-panel.tsx` uses `ButtonGroup` without `asChild`.

## Behavior changes



## Verify by hand

- Thread header button group: buttons join with shared borders as before.
