# scroll-area

2026-09-25, golden pair. `ScrollAreaScrollbar`/`Thumb` → `Scrollbar`/`Thumb`.

## Changed

- `src/components/ui/scroll-area.tsx`: base-nova shape; unused React import removed.
- `src/test-setup.ts` (new) + `vite.config.ts` `test.setupFiles`: jsdom has no `Element.getAnimations`, which Base UI's ScrollArea viewport calls; without the stub vitest reported 22 unhandled errors.
- Leftover scan clean: `grep -n "radix-ui\|@radix-ui"` finds nothing in this component's files.

## Left alone

- `workspace-rail.tsx` passes no `type` prop.

## Behavior changes

- **Scrollbar visibility:** Radix's default `type="hover"` showed the scrollbar only while hovering. The Base UI wrapper has no classes keyed on `data-hovering`/`data-scrolling`, so the scrollbar stays visible whenever the content overflows (as in base-nova). Not patched; `data-hovering:opacity-100` plus a base `opacity-0` on `ScrollBar` would restore hover-only.

## Verify by hand

- Workspace rail with many workspaces: wheel-scroll, drag the thumb, check the thumb appears.
