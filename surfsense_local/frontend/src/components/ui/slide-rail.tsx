import type { ReactNode } from "react"

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
      className="h-full min-h-0 overflow-hidden transition-[width] duration-200 ease-out motion-reduce:transition-none"
      style={{ width: open ? width : 0 }}
      inert={!open || undefined}
      aria-hidden={!open || undefined}
    >
      <div
        className={`flex h-full min-h-0 flex-col ${side === "end" ? "ml-auto" : "mr-auto"}`}
        style={{ width }}
      >
        {children}
      </div>
    </div>
  )
}

export { SlideRail }
