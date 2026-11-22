import type { ComponentProps } from "react"

import { cn } from "@/lib/utils"

/** The top row every dashboard column shares, so their titles sit on one line. */
export function ColumnHeader({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      className={cn("flex h-14 shrink-0 items-center gap-2 px-3", className)}
      {...props}
    />
  )
}
