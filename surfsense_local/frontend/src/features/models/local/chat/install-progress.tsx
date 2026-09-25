import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"
import type { InstallEvent } from "./api"
import { installView } from "./install-view"

export function InstallProgress({
  event,
  onCancel,
}: {
  event: InstallEvent
  onCancel: () => void
}) {
  const view = installView(event)
  const [announcement, setAnnouncement] = useState(view.label)
  const announcementText =
    view.percent === null
      ? view.label
      : intl.formatMessage(
          {
            id: "models_install_progress_announcement_status",
            defaultMessage: "{label} {percent, number, ::percent}",
          },
          {
            label: view.label,
            percent: view.percent / 100,
          }
        )

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
        {view.percent === null ? null : (
          <span className="ml-auto tabular-nums">
            {intl.formatMessage(
              {
                id: "models_install_progress_percent_status",
                defaultMessage: "{percent, number, ::percent}",
              },
              {
                percent: view.percent / 100,
              }
            )}
          </span>
        )}
      </div>
      <div
        className="h-1.5 overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-label={intl.formatMessage({
          id: "models_install_progress_aria",
          defaultMessage: "Model installation",
        })}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={view.percent ?? undefined}
      >
        {/* Keyed by phase so a new one starts its own bar rather than animating
            down from where the last ended. A full bar sliding back to empty is
            what read as the install failing and starting over. */}
        {view.percent === null ? (
          // Held, not animated. A phase with no figure is still a phase that is
          // going somewhere, and the line above it already says which; a bar
          // that moves without the work moving is the part that reads as noise.
          <div key={event.type} className="h-full rounded-full" />
        ) : (
          <div
            key={event.type}
            className="h-full rounded-full bg-primary transition-[width]"
            style={{ width: `${view.percent}%` }}
          />
        )}
      </div>
      <Button
        type="button"
        size="sm"
        variant="ghost"
        className="self-start"
        onClick={onCancel}
      >
        {intl.formatMessage({
          id: "models_install_progress_cancel_button",
          defaultMessage: "Cancel",
        })}
      </Button>
      <span className="sr-only" aria-live="polite">
        {announcement}
      </span>
    </div>
  )
}
