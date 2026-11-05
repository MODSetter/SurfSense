import type { ComponentProps } from "react"

import { cn } from "@/lib/utils"

/**
 * The window's grid: the workspace rail, then the columns. Shared with the
 * startup frame, so the dashboard's first frame lands on the frame's lines.
 */
export function DashboardShell({
  className,
  ...props
}: ComponentProps<"main">) {
  return (
    <main
      className={cn(
        "relative grid h-full min-w-292 grid-cols-[56px_minmax(0,1fr)] overflow-hidden bg-app-shell",
        className
      )}
      {...props}
    />
  )
}
