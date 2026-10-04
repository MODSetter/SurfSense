import type { ReactElement } from "react"

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"

// A held row still takes the pointer, or its reason could never be seen.
export const HINTED_ROW_CLASS = "data-disabled:pointer-events-auto"

/** A menu row's description, shown beside it on hover or focus. */
export function MenuItemHint({
  hint,
  children,
}: {
  hint: string
  children: ReactElement
}) {
  return (
    <Tooltip>
      <TooltipTrigger render={children} />
      <TooltipContent side="right">{hint}</TooltipContent>
    </Tooltip>
  )
}

// Base UI tooltips are visual only, so the row says its hint to screen readers.
export function HintedLabel({ label, hint }: { label: string; hint: string }) {
  return (
    <span className="min-w-0 flex-1">
      {label} <span className="sr-only">{hint}</span>
    </span>
  )
}
