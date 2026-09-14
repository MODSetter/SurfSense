import type { ReactNode } from "react"

export const MAIN_RAIL_WIDTH = 400
export const DETAIL_RAIL_WIDTH = 560

const RAIL_TWEEN =
  "min-w-0 transition-[width] duration-[240ms] ease-[cubic-bezier(0.4,0,0.2,1)] motion-reduce:transition-none"

function SlideRail({
  open,
  side = "end",
  width,
  children,
}: {
  open: boolean
  side?: "start" | "end"
  width: number
  children: ReactNode
}) {
  return (
    <div
      data-slot="slide-rail"
      className={`h-full min-h-0 shrink-0 overflow-hidden ${RAIL_TWEEN}`}
      style={{ width: open ? width : 0 }}
      inert={!open || undefined}
      aria-hidden={!open || undefined}
    >
      <div
        className={`flex h-full min-h-0 flex-col ${RAIL_TWEEN} ${side === "end" ? "ml-auto" : "mr-auto"}`}
        style={{ width }}
      >
        {children}
      </div>
    </div>
  )
}

export { SlideRail }
