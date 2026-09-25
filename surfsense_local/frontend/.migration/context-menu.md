# context-menu

2026-09-25, golden pair (base-nova) with local edits reapplied.

## Changed

- `src/components/ui/context-menu.tsx`: base-nova shape; local icons kept; `cn-*` hooks dropped. The local `modal = false` default is gone: Base UI's ContextMenu has no `modal` prop.
- `workspace-rail.tsx`: `ContextMenuTrigger asChild` → `render`; two `ContextMenuItem onSelect` → `onClick`; `onCloseAutoFocus` preventDefault → `finalFocus={false}`.
- Leftover scan clean: `grep -n "radix-ui\|@radix-ui"` finds nothing in this component's files.

## Left alone

- Nothing related.

## Behavior changes

- Main content now opens `side="right" align="start" alignOffset={4}` from the pointer (base-nova default); the menu still starts at the cursor.
- The local `modal = false` default can't be carried over: Base UI's ContextMenu has no `modal` option. Check that the rail behind still reacts as expected while the menu is open.

## Verify by hand

- Right-click a workspace icon: the menu opens at the cursor; Rename and Delete work; Esc closes.
- Right-click near the window's right or bottom edge: the menu flips to stay on screen.
