# combobox

2026-09-25, engine. Local combobox kept; its Radix Popover swapped for Base UI's.

## Changed

- `src/components/ui/combobox.tsx`: `Popover.Anchor asChild` → a ref on `InputGroup` passed to the Positioner's `anchor`; `Popover.Trigger asChild` → `render`; `onOpenAutoFocus`/`onCloseAutoFocus` preventDefault → `initialFocus={false}`/`finalFocus={false}`; `--radix-popover-*` vars → Base UI vars. Header comment updated.
- Not replaced with shadcn's Base UI Combobox: the one caller (`connection-form.tsx`) relies on the local API: keyword filtering, a `showAll` filter while closed, free-text entry. Moving to Base UI's Combobox is a separate refactor.
- Leftover scan clean. The file contains literal NUL characters (the `keywords.join` key, committed before this work), so plain `grep` treats it as binary; scanned with `grep -a`.

## Left alone

- `connection-form.tsx`: no changes needed.

## Behavior changes

- Not observed in tests: whether Base UI's popover closes on focus moving from the chevron to the input. The input reopens it on click or typing either way.

## Verify by hand

- Settings → Models → Connect a server → Provider: type to filter, arrow keys + Enter pick, Esc closes, the chevron toggles, typing a custom URL still works.
- Inside the dialog, the provider list scrolls with the wheel.
