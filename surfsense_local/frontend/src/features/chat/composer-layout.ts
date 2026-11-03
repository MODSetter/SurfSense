import { cn } from "@/lib/utils"

// The composer's geometry, shared by ChatComposer and the startup frame's
// outline of it, so the box the frame draws is the box that replaces it.

export type ComposerPlacement = "center" | "bottom"

export const COMPOSER_CLASS = "relative mx-auto w-full max-w-2xl"

// No top padding: the text scrolls up to the border, not to a strip above
// it, and holds that space in its own padding instead.
export function composerBoxClass(placement: ComposerPlacement) {
  return cn(
    "relative rounded-2xl border bg-card px-1.5 pb-1.5 shadow-sm",
    placement === "bottom" && "flex items-end gap-2"
  )
}

// One line tall at rest: an outline holds a line of nothing to match it.
export function composerInputClass(placement: ComposerPlacement) {
  return cn(
    "max-h-44 resize-none bg-transparent px-2 pt-4 pb-2.5 text-sm outline-none placeholder:text-muted-foreground",
    placement === "center" ? "block min-h-12 w-full" : "min-h-10 flex-1"
  )
}

// At least as tall as its icon-lg buttons, so the outline, which has none,
// keeps the height they give it.
export const COMPOSER_CONTROLS_CLASS =
  "flex min-h-9 items-center justify-between gap-2"

export const COMPOSER_FOOTER_CLASS =
  "mt-1 flex min-h-7 items-center justify-between gap-3 px-2"
