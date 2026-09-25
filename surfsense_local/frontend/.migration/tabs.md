# tabs

2026-09-25, engine on the local file (local tabs are hand-styled, not stock radix-nova).

## Changed

- `src/components/ui/tabs.tsx`: `Trigger` → `Tab`, `Content` → `Panel`; `data-[state=active]:` → `data-active:`; `aria-disabled:` added next to `disabled:`.
- `score-screen.tsx`: its `TabsTrigger` classes `data-[state=active]:` → `data-active:`.
- Leftover scan clean: `grep -n "radix-ui\|@radix-ui"` finds nothing in this component's files.

## Left alone

- Nothing related.

## Behavior changes

- **Activation:** Radix tabs switched on arrow-key focus; Base UI switches only on Enter/Space or click (manual). Not patched. `<TabsList activateOnFocus>` restores the old behaviour if wanted.

## Verify by hand

- Quiz score screen: click Correct/Missed/Skipped; the active pill is highlighted.
- Arrow keys move focus between tabs; Enter selects (this is the change).
