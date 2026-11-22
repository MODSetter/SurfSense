import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

/**
 * Pins a toggle to one of the columns' top corners, centred on the 56 px
 * heading line, where that side's column heading would hold it.
 */
export function CornerToggle({
  side,
  children,
}: {
  side: "start" | "end"
  children: ReactNode
}) {
  return (
    <div
      className={cn(
        "absolute top-3.5 z-10 flex",
        // 8 px in from either side: the sidebar's heading pulls its toggle
        // 4 px into its 12 px padding, and the right mirrors it.
        side === "start" ? "left-2" : "right-2"
      )}
    >
      {children}
    </div>
  )
}

/** Keeps the corner toggle's room on a heading's line, so nothing runs under it. */
export function CornerToggleSlot({ className }: { className?: string }) {
  return <span aria-hidden className={cn("block size-7 shrink-0", className)} />
}
