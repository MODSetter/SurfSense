import { useSyncExternalStore } from "react"

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

const formatter = new Intl.RelativeTimeFormat(undefined, {
  numeric: "auto",
  style: "long",
})
const units: [number, Intl.RelativeTimeFormatUnit][] = [
  [60, "minute"],
  [24, "hour"],
  [7, "day"],
  [4.345, "week"],
  [12, "month"],
  [Number.POSITIVE_INFINITY, "year"],
]

// Sidebar rows: "45s", "5m", "2h", "3d", "2w", "4mo", "1y"; the tooltip has the date.
const compactUnits: [number, string][] = [
  [60, "s"],
  [60, "m"],
  [24, "h"],
  [7, "d"],
  [4.345, "w"],
  [12, "mo"],
  [Number.POSITIVE_INFINITY, "y"],
]

let now = Date.now()
let clock: number | undefined
const listeners = new Set<() => void>()

function subscribe(listener: () => void) {
  listeners.add(listener)
  if (listeners.size === 1) {
    now = Date.now()
    // 10s so the compact seconds count moves; the long form only changes by the minute.
    clock = window.setInterval(() => {
      now = Date.now()
      listeners.forEach((notify) => {
        notify()
      })
    }, 10_000)
  }
  return () => {
    listeners.delete(listener)
    if (listeners.size === 0) {
      window.clearInterval(clock)
      clock = undefined
    }
  }
}

function formatRelativeTime(date: Date, currentTime: number) {
  const seconds = (date.getTime() - currentTime) / 1000
  if (Math.abs(seconds) < 60) {
    return "just now"
  }

  let value = seconds / 60
  for (const [limit, unit] of units) {
    if (Math.abs(value) < limit) {
      return formatter.format(Math.round(value), unit)
    }
    value /= limit
  }
}

function formatCompactTime(date: Date, currentTime: number) {
  let value = Math.max(0, (currentTime - date.getTime()) / 1000)
  for (const [limit, unit] of compactUnits) {
    if (value < limit) return `${Math.max(1, Math.floor(value))}${unit}`
    value /= limit
  }
}

export function RelativeTime({
  date,
  compact = false,
  className,
}: {
  date: Date
  compact?: boolean
  className?: string
}) {
  const currentTime = useSyncExternalStore(
    subscribe,
    () => now,
    () => now
  )
  const exactTime = date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  })

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <time
          dateTime={date.toISOString()}
          className={cn(
            "inline-flex h-7 cursor-default items-center text-xs select-none",
            className
          )}
        >
          {compact
            ? formatCompactTime(date, currentTime)
            : formatRelativeTime(date, currentTime)}
        </time>
      </TooltipTrigger>
      <TooltipContent>{exactTime}</TooltipContent>
    </Tooltip>
  )
}
