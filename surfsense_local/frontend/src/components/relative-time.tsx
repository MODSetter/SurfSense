import { useSyncExternalStore } from "react"

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

const units: [number, Intl.RelativeTimeFormatUnit][] = [
  [60, "minute"],
  [24, "hour"],
  [7, "day"],
  [4.345, "week"],
  [12, "month"],
  [Number.POSITIVE_INFINITY, "year"],
]

// Sidebar rows: "5m", "2h", "3d", "2w", "4mo", "1y"; the tooltip has the date.
const compactUnits: [number, (count: number) => string][] = [
  [
    60,
    (count) =>
      intl.formatMessage(
        {
          id: "app_relative_time_compact_minutes_label",
          defaultMessage: "{count, number}m",
        },
        { count }
      ),
  ],
  [
    24,
    (count) =>
      intl.formatMessage(
        {
          id: "app_relative_time_compact_hours_label",
          defaultMessage: "{count, number}h",
        },
        { count }
      ),
  ],
  [
    7,
    (count) =>
      intl.formatMessage(
        {
          id: "app_relative_time_compact_days_label",
          defaultMessage: "{count, number}d",
        },
        { count }
      ),
  ],
  [
    4.345,
    (count) =>
      intl.formatMessage(
        {
          id: "app_relative_time_compact_weeks_label",
          defaultMessage: "{count, number}w",
        },
        { count }
      ),
  ],
  [
    12,
    (count) =>
      intl.formatMessage(
        {
          id: "app_relative_time_compact_months_label",
          defaultMessage: "{count, number}mo",
        },
        { count }
      ),
  ],
  [
    Number.POSITIVE_INFINITY,
    (count) =>
      intl.formatMessage(
        {
          id: "app_relative_time_compact_years_label",
          defaultMessage: "{count, number}y",
        },
        { count }
      ),
  ],
]

// Only triggers re-renders every 10s; never caches the time itself.
let clock: number | undefined
const listeners = new Set<() => void>()

function subscribe(listener: () => void) {
  listeners.add(listener)
  if (listeners.size === 1) {
    clock = window.setInterval(() => {
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

// Bucketed to the second so repeated calls stay comparable (required by
// useSyncExternalStore), but computed fresh each time — never cached.
function getSnapshot() {
  return Math.floor(Date.now() / 1000)
}

function formatRelativeTime(date: Date, currentTime: number) {
  const seconds = (date.getTime() - currentTime) / 1000
  if (Math.abs(seconds) < 60) {
    return intl.formatMessage({
      id: "app_relative_time_just_now_label",
      defaultMessage: "just now",
    })
  }

  let value = seconds / 60
  for (const [limit, unit] of units) {
    if (Math.abs(value) < limit) {
      return intl.formatRelativeTime(Math.round(value), unit, {
        numeric: "auto",
        style: "long",
      })
    }
    value /= limit
  }
}

function formatCompactTime(date: Date, currentTime: number) {
  const seconds = Math.max(0, (currentTime - date.getTime()) / 1000)
  if (seconds < 60) {
    return intl.formatMessage({
      id: "app_relative_time_compact_now_label",
      defaultMessage: "now",
    })
  }

  let value = seconds / 60
  for (const [limit, label] of compactUnits) {
    if (value < limit) return label(Math.max(1, Math.floor(value)))
    value /= limit
  }
}

export function RelativeTime({
  id,
  date,
  compact = false,
  showTooltip = true,
  className,
}: {
  id?: string
  date: Date
  compact?: boolean
  showTooltip?: boolean
  className?: string
}) {
  const currentTime =
    useSyncExternalStore(subscribe, getSnapshot, getSnapshot) * 1000
  const exactTime = intl.formatDate(date, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  })

  const time = (
    <time
      id={id}
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
  )

  if (!showTooltip) return time

  return (
    <Tooltip>
      <TooltipTrigger asChild>{time}</TooltipTrigger>
      <TooltipContent>{exactTime}</TooltipContent>
    </Tooltip>
  )
}
