import type { ReactNode } from "react"

import { intl } from "@/i18n/intl"

// The right column: live resource usage on top, then Studio's generate
// control above the artifact list, and an inspected citation or artifact
// swaps out for the whole panel. There used to be a Sources tab here too —
// sources now live in the left sidebar, so this panel has no switcher.
export function RightPanel({
  inspect,
  usage,
  studio,
  artifacts,
}: {
  inspect: ReactNode
  usage: ReactNode
  studio: ReactNode
  artifacts: ReactNode
}) {
  if (inspect) return inspect

  return (
    <aside
      className="flex h-full min-h-0 min-w-0 flex-col gap-5 overflow-hidden border-l bg-background select-none"
      aria-label={intl.formatMessage({
        id: "dashboard_right_panel_aria",
        defaultMessage: "Workspace artifacts",
      })}
    >
      {/* Usage sits where the left sidebar's "SurfSense" header does, so
          Studio's heading now starts below that line rather than on it. */}
      <div className="shrink-0 px-3 pt-3">{usage}</div>
      <header className="-mt-2 shrink-0 space-y-6 px-3 pb-3">
        <h2 className="truncate px-1 font-heading text-lg font-medium text-foreground select-none">
          Studio
        </h2>
        {studio}
      </header>
      <div className="min-h-0 min-w-0 flex-1 overflow-hidden px-3 pb-2">
        {artifacts}
      </div>
    </aside>
  )
}
