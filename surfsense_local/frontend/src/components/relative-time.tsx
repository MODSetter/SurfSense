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

let now = Date.now()
let clock: number | undefined
const listeners = new Set<() => void>()

function subscribe(listener: () => void) {
  listeners.add(listener)
  if (listeners.size === 1) {
    now = Date.now()
    clock = window.setInterval(() => {
      now = Date.now()
      listeners.forEach((notify) => {
        notify()
      })
    }, 60_000)
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

export function RelativeTime({
  date,
  className,
}: {
  date: Date
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
            "inline-flex h-7 cursor-default items-center text-xs",
            className
          )}
        >
          {formatRelativeTime(date, currentTime)}
        </time>
      </TooltipTrigger>
      <TooltipContent>{exactTime}</TooltipContent>
    </Tooltip>
  )
}
