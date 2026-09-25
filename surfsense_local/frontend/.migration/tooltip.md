# tooltip

2026-09-25, golden pair; heavily customised wrapper hand-merged.

## Changed

- `src/components/ui/tooltip.tsx`: `Portal > Positioner > Popup`. Kept local choices: popover colours + border, no arrow, `pointer-events-none`, 500 ms provider delay (`delayDuration` → `delay`). Radix's provider-wide `disableHoverableContent` is now `disableHoverablePopup = true` on each `Tooltip`. The `delayed-open`-only animation is now `data-open:animate-in … data-instant:animate-none`. `collisionPadding` is forwarded to the Positioner (six call sites pass it).
- 14 call sites: `TooltipTrigger asChild` → `render={…}`.
- Tests (`artifact-list`, `source-upload`, `studio-panel`, `download-chat-models`): `findByRole("tooltip", { name })` → `findByText`, because Base UI popups have no tooltip role.
- Leftover scan clean: `grep -n "radix-ui\|@radix-ui"` finds nothing in this component's files.

## Left alone

- Nothing related.

## Behavior changes

- **Accessibility:** Base UI tooltips are visual only. No `role="tooltip"`, no `aria-describedby` on the trigger. Text that lived only in a tooltip is no longer announced. Affected: the Studio format explanations ("Needs an image model", format descriptions), the retry hints, and the Ctrl/Cmd real-error reveal. Their triggers have `aria-label`s, but those don't carry the full tooltip text.
- Skip-delay grouping (Radix `skipDelayDuration`) is replaced by Base UI's provider `timeout`, default 400 ms.

## Verify by hand

- Hover an icon in the chat composer: tooltip after ~0.5 s, no arrow, popover styling.
- Move quickly between rail icons: the second tooltip opens instantly without animating.
- Tab to a tooltip trigger: the tooltip opens on focus.
- Sources/Studio failed rows: plain hover shows the generic hint; Ctrl/Cmd+hover shows the real error.
