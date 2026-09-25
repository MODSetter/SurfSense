# checkbox

2026-09-25, golden pair, local classes kept.

## Changed

- `src/components/ui/checkbox.tsx`: Base UI `Checkbox`. Its Root renders a `<span>`, so `disabled:` classes became `data-disabled:` and `data-[state=checked]:` became `data-checked:`.
- Leftover scan clean: `grep -n "radix-ui\|@radix-ui"` finds nothing in this component's files.

## Left alone

- `sources-panel.tsx` uses it with boolean `checked`; no `"indeterminate"` call sites.

## Behavior changes



## Verify by hand

- Sources panel: select-all and per-row checkboxes toggle, show the tick, and look dimmed when disabled.
