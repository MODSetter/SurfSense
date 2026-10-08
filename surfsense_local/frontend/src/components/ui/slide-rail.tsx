import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

export const MAIN_RAIL_WIDTH = 400
export const DETAIL_RAIL_WIDTH = 560

const RAIL_TWEEN =
  "min-w-0 transition-[width] duration-[240ms] ease-[cubic-bezier(0.4,0,0.2,1)] motion-reduce:transition-none"

function SlideRail({
  open,
  side = "end",
  width,
  animate = true,
  children,
}: {
  open: boolean
  side?: "start" | "end"
  width: number
  // False while its edge is dragged, so the rail follows the pointer.
  animate?: boolean
  children: ReactNode
}) {
  const tween = cn(RAIL_TWEEN, !animate && "transition-none")
  return (
    <div
      data-slot="slide-rail"
      className={cn("h-full min-h-0 shrink-0 overflow-hidden", tween)}
      style={{ width: open ? width : 0 }}
      inert={!open || undefined}
      aria-hidden={!open || undefined}
    >
      <div
        className={cn(
          "flex h-full min-h-0 flex-col",
          tween,
          side === "end" ? "ml-auto" : "mr-auto"
        )}
        style={{ width }}
      >
        {children}
      </div>
    </div>
  )
}

export { SlideRail }
