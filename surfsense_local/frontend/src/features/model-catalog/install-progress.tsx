import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import type { InstallEvent } from "./api"

const bytes = (value: number) =>
  new Intl.NumberFormat(undefined, {
    style: "unit",
    unit: "gigabyte",
    maximumFractionDigits: 1,
  }).format(value / 1e9)

function eventLabel(event: InstallEvent) {
  if (event.type === "downloading") {
    const percent =
      event.total > 0
        ? Math.min(100, Math.round((event.completed / event.total) * 100))
        : null
    return {
      label: event.message || "Downloading",
      detail:
        event.total > 0
          ? `${bytes(event.completed)} of ${bytes(event.total)}`
          : null,
      percent,
    }
  }
  const message = "message" in event ? event.message : undefined
  return {
    label:
      message ||
      (event.type === "starting"
        ? "Starting"
        : event.type === "verifying"
          ? "Verifying"
          : event.type === "selecting"
            ? "Selecting"
            : event.type === "complete"
              ? "Complete"
              : "Install failed"),
    detail: null,
    percent: event.type === "complete" ? 100 : null,
  }
}

export function InstallProgress({
  event,
  onCancel,
}: {
  event: InstallEvent
  onCancel: () => void
}) {
  const view = eventLabel(event)
  const [announcement, setAnnouncement] = useState(view.label)
  const announcementText = `${view.label}${
    view.percent === null ? "" : ` ${view.percent}%`
  }`

  useEffect(() => {
    const timeout = window.setTimeout(
      () => setAnnouncement(announcementText),
      750
    )
    return () => window.clearTimeout(timeout)
  }, [announcementText])

  return (
    <div className="flex flex-col gap-2 rounded-lg bg-muted/60 p-3">
      <div className="flex items-center gap-2 text-xs">
        <span className="animate-spin">
          <Spinner className="size-3.5" />
        </span>
        <span>{view.label}</span>
        {view.detail ? (
          <span className="text-muted-foreground">{view.detail}</span>
        ) : null}
        {view.percent !== null ? (
          <span className="ml-auto tabular-nums">{view.percent}%</span>
        ) : null}
      </div>
      <div
        className="h-1.5 overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-label="Model installation"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={view.percent ?? undefined}
      >
        <div
          className="h-full rounded-full bg-primary transition-[width]"
          style={{ width: `${view.percent ?? 8}%` }}
        />
      </div>
      <Button
        type="button"
        size="sm"
        variant="ghost"
        className="self-start"
        onClick={onCancel}
      >
        Cancel
      </Button>
      <span className="sr-only" aria-live="polite">
        {announcement}
      </span>
    </div>
  )
}
