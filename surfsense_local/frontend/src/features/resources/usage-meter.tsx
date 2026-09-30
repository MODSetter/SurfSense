import { useId } from "react"

import { cn } from "@/lib/utils"

import type { UsageRow } from "./usage-rows"

// Width eases between polls so a reading two seconds on reads as motion, not a jump.
const SEGMENT =
  "h-full transition-[width] duration-500 ease-out motion-reduce:transition-none"

/** One row of the panel's grid: label, bar, the machine's figure, the app's. */
export function UsageMeter({ row }: { row: UsageRow }) {
  const labelId = useId()
  return (
    <div data-row className="col-span-4 grid grid-cols-subgrid items-center">
      <span id={labelId} className="text-secondary-foreground">
        {row.label}
      </span>
      <div
        role="meter"
        aria-labelledby={labelId}
        aria-valuemin={0}
        aria-valuemax={row.max}
        aria-valuenow={row.now}
        aria-valuetext={row.valueText}
        className="flex h-1.5 overflow-hidden rounded-full bg-muted"
      >
        <div
          data-segment="app"
          className={cn(SEGMENT, "bg-chart-1")}
          style={{ width: `${row.appShare}%` }}
        />
        <div
          data-segment="other"
          className={cn(SEGMENT, "bg-chart-3")}
          style={{ width: `${row.otherShare}%` }}
        />
      </div>
      <span
        aria-hidden
        className={cn(
          "text-right tabular-nums",
          row.nearlyFull ? "text-warning" : "text-secondary-foreground"
        )}
      >
        {row.machine}
      </span>
      <span
        aria-hidden
        className="flex items-center justify-end gap-1.5 font-medium text-foreground tabular-nums"
      >
        {row.app === null ? (
          "—"
        ) : (
          <>
            <span className="size-1.5 shrink-0 rounded-full bg-chart-1" />
            {row.app}
          </>
        )}
      </span>
    </div>
  )
}
