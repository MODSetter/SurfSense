# Base UI in the desktop frontend

`surfsense_local/frontend` builds its `components/ui/` on Base UI (shadcn
`base-nova`). `surfsense_web` is still on Radix (`new-york`): none of this
applies there.

These are the rules that compile fine and still break. Check
`node_modules/@base-ui/react/**/*.d.ts` or its `docs/` for anything else.

## Composition

- `render`, not `asChild`: `<TooltipTrigger render={<Button />} />`.
- A trigger or `Button` rendering a non-button element needs
  `nativeButton={false}`.
- A link styled as a button is a real `<a>` with `buttonVariants(...)`. Base
  UI's `Button` gives whatever it renders `role="button"`.

## Menus

- Items act on `onClick`. `onSelect` still typechecks (it is a DOM prop) and
  never fires.
- `DropdownMenuLabel` / `ContextMenuLabel` go inside a `…Group`. Outside one,
  the menu throws "MenuGroupContext is missing".
- Items close the menu on click. Checkbox and radio items stay open unless
  given `closeOnClick`.
- Keep focus in a field opened from a menu with `finalFocus={false}` on the
  content, not a Radix `onCloseAutoFocus` handler.

## Dialogs

- Focus on open and close is `initialFocus` / `finalFocus` (an element, a ref,
  `false`, or a function), not `onOpenAutoFocus` / `onCloseAutoFocus`.
- `AlertDialogAction` closes the dialog unless its click handler calls
  `event.preventDefault()`. The local wrapper keeps this Radix contract on
  purpose; the stock base-nova Action does not close at all.
- Keep "open" apart from "what it shows". Closing only sets `open` false;
  clear the data in `onOpenChangeComplete`, which fires once the exit
  animation is done. `open={target !== null}` with content read from
  `target` blanks the dialog before it fades. A dialog mounted only while it
  has data (`{target ? <Dialog/> : null}`) is unmounted the same way, from
  `onOpenChangeComplete`, never on close.
- A dialog opened from inside another renders inside its `DialogContent`,
  so Base UI nests it. A dialog the whole app can raise over any dialog
  goes in `APP_DIALOGS` in `main.tsx` instead of being mounted: the deepest
  open popup renders it, so it remounts as dialogs open and close and keeps
  its state in a store (see `features/egress/ask-egress.ts`).
- A nested dialog renders no backdrop. The parent dims and shrinks through
  `data-nested-dialog-open` and `--nested-dialogs`, already in the wrappers.
- A popup inside a modal dialog (the combobox, through `container`) portals
  into a host element within the dialog, which hides everything outside itself from
  assistive technology.

## Tooltips and tabs

- Tooltips are visual only: no `role="tooltip"`, no `aria-describedby`. Never
  put text a user needs only in a tooltip; the trigger needs its own
  `aria-label`.
- Tabs switch on Enter, Space or click, not on arrow focus. Add
  `activateOnFocus` to the `TabsList` when the panels show instantly (local
  state); leave it off when a panel loads.

## Tests

- Menus and popovers mount after the click: query their items with
  `findByRole`, not `getByRole`. Check that something is absent only after a
  present item has been found.
- Tooltips have no role: find them by text.
- `src/test-setup.ts` stubs `Element.getAnimations`, which jsdom lacks and
  Base UI calls.
