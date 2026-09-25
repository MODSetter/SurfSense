"use client"

import { Checkbox as CheckboxPrimitive } from "@base-ui/react/checkbox"
import { cn } from "@/lib/utils"

import { CheckIcon } from "@/components/ui/icons"

function Checkbox({ className, ...props }: CheckboxPrimitive.Root.Props) {
  return (
    <CheckboxPrimitive.Root
      data-slot="checkbox"
      className={cn(
        "peer relative flex size-4 shrink-0 items-center justify-center rounded-[4px] border border-input transition-colors outline-none group-has-disabled/field:opacity-50 group-has-[:focus-visible]/field-label:ring-0 group-has-[:focus-visible]/field-label:not-data-checked:border-input after:absolute after:-inset-x-3 after:-inset-y-2 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 aria-invalid:aria-checked:border-primary dark:bg-input/30 dark:aria-invalid:border-destructive/50 dark:aria-invalid:ring-destructive/40 data-checked:border-primary data-checked:bg-primary data-checked:text-primary-foreground group-has-[:focus-visible]/field-label:data-checked:border-primary dark:data-checked:bg-primary",
        // On uncheck the fill waits for the tick to undraw (the indicator's
        // 150ms exit); fading together leaves a dark tick on a dark box.
        "not-data-checked:[transition:background-color_150ms_ease-out_150ms,border-color_150ms_ease-out_150ms]",
        className
      )}
      {...props}
    >
      <CheckboxPrimitive.Indicator
        data-slot="checkbox-indicator"
        // Tick draws left to right and undraws right to left. Its own fixed
        // colour, since the box's text colour flips the instant it unchecks.
        className="grid place-content-center text-primary-foreground transition-[clip-path] duration-400 ease-out [clip-path:inset(0)] data-ending-style:duration-150 data-ending-style:[clip-path:inset(0_100%_0_0)] data-starting-style:[clip-path:inset(0_100%_0_0)] motion-reduce:transition-none [&>svg]:size-3.5"
      >
        <CheckIcon strokeWidth={3} />
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  )
}

export { Checkbox }
