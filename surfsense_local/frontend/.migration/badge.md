# badge

2026-09-25, golden pair. `Slot` → `useRender` + `mergeProps`.

## Changed

- `src/components/ui/badge.tsx`: base-nova shape; local `warning` variant kept. `data-slot` now comes from `useRender` state.
- Leftover scan clean: `grep -n "radix-ui\|@radix-ui"` finds nothing in this component's files.

## Left alone

- Badge call sites: none used `asChild`.

## Behavior changes



## Verify by hand

- Model cards and the Models settings list: badges render with the same colours, including the warning badge.
