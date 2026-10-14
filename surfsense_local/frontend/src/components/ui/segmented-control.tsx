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
        // The pill tabs' look (components/ui/tabs.tsx), as a choice of values rather than tabs.
        "relative inline-flex items-center overflow-hidden rounded-lg bg-muted p-0.5 text-muted-foreground",
        "[&_svg]:text-current",
        "[&_label]:text-muted-foreground [&_label]:transition-colors",
        "[&_label:hover:not(:has(:checked))]:text-foreground",
        "[&_label:has(:checked)]:text-accent-foreground",
        "[&_label:has(:checked)_svg]:text-accent-foreground",
        "**:aria-selected:text-accent-foreground",
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
        // Still slides while choosing a theme pauses every other transition.
        data-keep-transition
        className="pointer-events-none absolute inset-y-0.5 left-0.5 rounded-md bg-card transition-transform duration-250 ease-out motion-reduce:transition-none dark:bg-accent"
        style={{
          // Inside the bar's 2px padding on each side.
          width: `calc((100% - 4px) / ${count})`,
          translate: `${selectedIndex * 100}%`,
        }}
      />
      {children}
    </div>
  )
}
