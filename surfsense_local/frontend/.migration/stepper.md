# stepper

2026-09-25, engine (custom component, not shadcn).

## Changed

- `src/components/ui/stepper.tsx`: `StepperTrigger` moved from `Slot`/`asChild` to the `@base-ui/react/button` primitive (`render` prop). No caller used `asChild`.
- Leftover scan clean: `grep -n "radix-ui\|@radix-ui"` finds nothing in this component's files.

## Left alone

- `StepperIndicator` keeps its own `asChild` prop: it only swaps children and never used Radix.
- The stepper's `data-state` attributes are its own, not Radix's; unchanged.

## Behavior changes



## Verify by hand

- Onboarding: the step bar fills as you advance; if a trigger is clickable it moves to that step.
