# label

2026-09-25, golden pair. No Base UI Label: native `<label>`.

## Changed

- `src/components/ui/label.tsx`: `LabelPrimitive.Root` → `<label>`, same classes.
- Leftover scan clean: `grep -n "radix-ui\|@radix-ui"` finds nothing in this component's files.

## Left alone

- Nothing related.

## Behavior changes

- Radix Label prevented text selection on double-click; the native label does not.

## Verify by hand

- Click each settings field label: it focuses its input.
