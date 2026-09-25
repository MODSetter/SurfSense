# radio-group

2026-09-25, golden pair. Group from `radio-group`, items from `radio`.

## Changed

- `src/components/ui/radio-group.tsx`: `RadioGroupPrimitive` (callable) + `Radio.Root`/`Radio.Indicator`. Dead `disabled:` classes on the span root changed to `data-disabled:`.
- Leftover scan clean: `grep -n "radix-ui\|@radix-ui"` finds nothing in this component's files.

## Left alone

- No app file imports RadioGroup today.

## Behavior changes



## Verify by hand

- None in the app; check any future use for arrow-key movement between options.
