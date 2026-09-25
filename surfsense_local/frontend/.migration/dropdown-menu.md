# dropdown-menu

2026-09-25, golden pair (base-nova) with local edits reapplied.

## Changed

- `src/components/ui/dropdown-menu.tsx`: `DropdownMenu` → `Menu`; Content → `Portal > Positioner > Popup`; `Label` → `GroupLabel`; `Sub*` → `Submenu*`. Kept: `modal = false` default, local `CheckIcon`/`ChevronRightIcon`, no `cn-*` hook classes. `--radix-dropdown-menu-*` vars → `--available-height`, `--anchor-width`, `--transform-origin`.
- `onSelect` → `onClick` on 18 `DropdownMenuItem`s (artifact-list, sources-panel, score-screen, model-picker, chats-dialog, thread-panel). `onSelect` still typechecks on Base UI items (it's a DOM prop) but never fires.
- `artifact-list.tsx`: the checkbox item's `onSelect={(e) => e.preventDefault()}` (keep open) removed; Base UI checkbox items stay open by default. The `DropdownMenuLabel` sat outside a group and would throw ("MenuGroupContext is missing"); moved into its group.
- `model-picker.tsx`: `closeOnClick` added on `DropdownMenuRadioItem`; Base UI radio items stay open by default and the test suite expects the picker to close on pick. Stray `nativeButton={false}` on a native `<button>` trigger removed.
- `chats-dialog.tsx`: `onCloseAutoFocus` preventDefault → `finalFocus={false}`. `thread-panel.tsx`: conditional version → `finalFocus={() => …}`.
- Trigger classes `data-[state=open]:` → `data-popup-open:` (artifact-list, chats-dialog, sources-panel).
- Tests: menu items are queried with `findByRole` (Base UI mounts the popup asynchronously after a pointer click); two absence checks reordered to run after the menu is confirmed open.
- Leftover scan clean: `grep -n "radix-ui\|@radix-ui"` finds nothing in this component's files.

## Left alone

- Nothing related.

## Behavior changes

- Items close the menu on click (same as Radix). Checkbox items stay open (as before, via default). Radio items close via the explicit `closeOnClick`.
- Menus loop keyboard focus by default (Radix `loop` was off).
- Popups mount one tick later after a pointer click.

## Verify by hand

- Artifact row ⋯ menu: Open/Regenerate/Delete each act and close the menu.
- Studio type filter: tick two types without the menu closing; Clear filter resets.
- Model picker: type to search, pick a model: the menu closes and the model changes; Manage models opens settings.
- Chats dialog ⋯ → Rename: the rename field keeps focus (the menu does not steal it back).
- Keyboard: open with Enter, arrow through items, typeahead, Esc closes and returns focus.
