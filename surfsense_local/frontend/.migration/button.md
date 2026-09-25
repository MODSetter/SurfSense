# button

2026-09-25, golden pair (radix-nova → base-nova, three-way merge). Migrated to the real `@base-ui/react/button` primitive.

## Changed

- `src/components/ui/button.tsx`: `Slot`/`asChild` replaced by `ButtonPrimitive` (`render` prop). Local `xl`, `2xl`, `icon-xl`, `icon-2xl` sizes and `cursor-pointer` kept. `data-variant` and `data-size` restored (base-nova drops them; `left-sidebar.test.tsx:42` reads `data-variant`).
- `src/features/studio/artifact-panel.tsx`: the download link was `<Button asChild><a download/></Button>`. Base UI's Button puts `role="button"` on a non-button element, so it is now a plain `<a>` styled with `buttonVariants`. It keeps its link role.
- Leftover scan clean: `grep -n "radix-ui\|@radix-ui"` finds nothing in this component's files.

## Left alone

- `button-group.tsx` imports nothing from Button; migrated separately.

## Behavior changes

- Any `<Button render={<a/>}>` needs `nativeButton={false}` and is announced as a button. Use `buttonVariants` on a real `<a>` for links.

## Verify by hand

- Tab through a dialog footer: Buttons focus, Enter/Space activate.
- Studio → open an artifact → Download icons: they are links (right-click shows link options) and download the file.
