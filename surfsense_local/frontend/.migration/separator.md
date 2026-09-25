# separator

2026-09-25, golden pair. Callable `@base-ui/react/separator`.

## Changed

- `src/components/ui/separator.tsx`: `SeparatorPrimitive.Root` → `SeparatorPrimitive`; `decorative` dropped (no call site passed it).
- Leftover scan clean: `grep -n "radix-ui\|@radix-ui"` finds nothing in this component's files.

## Left alone

- Nothing related.

## Behavior changes

- Base UI always renders `role="separator"`; Radix defaulted to `decorative` (no role). Screen readers may now announce separators.

## Verify by hand

- Menus and the button group: separators still draw at the same place.
