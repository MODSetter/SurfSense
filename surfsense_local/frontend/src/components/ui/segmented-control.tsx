import type { ComponentProps } from "react"

import { cn } from "@/lib/utils"

export function SegmentedControl({
  count,
  selectedIndex,
  className,
  children,
  ...props
}: ComponentProps<"div"> & {
  count: number
  selectedIndex: number
}) {
  return (
    <div
      className={cn(
        "relative inline-flex items-center overflow-hidden rounded-md border bg-muted/80 text-muted-foreground",
        "[&_svg]:text-current",
        "[&_label]:text-muted-foreground [&_label]:transition-colors",
        "[&_label:hover:not(:has(:checked))]:text-foreground",
        "[&_label:has(:checked)]:text-accent-foreground",
        "[&_label:has(:checked)_svg]:text-accent-foreground",
        "[&_[aria-selected=true]]:text-accent-foreground",
        "[&_[aria-selected=true]_svg]:text-accent-foreground",
        "[&_[aria-selected=false]:hover]:text-foreground",
        "[&_[aria-selected=false]:hover_svg]:text-foreground",
        className
      )}
      {...props}
    >
      <span
        aria-hidden="true"
        data-slot="segmented-control-indicator"
        className="pointer-events-none absolute inset-y-0 left-0 rounded-md border border-input bg-accent shadow-sm transition-transform duration-300 ease-out motion-reduce:transition-none"
        style={{
          width: `calc(100% / ${count})`,
          translate: `${selectedIndex * 100}%`,
        }}
      />
      {children}
    </div>
  )
}
