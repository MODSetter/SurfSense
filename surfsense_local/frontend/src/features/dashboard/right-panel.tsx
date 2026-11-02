import type { ReactNode } from "react"

import { ColumnHeader } from "@/components/ui/column-header"
import { intl } from "@/i18n/intl"

// The right column: Studio's generate control sits above the artifact
// list, and an inspected citation or artifact swaps out for the whole panel.
// There used to be a Sources tab here too — sources now live in the left
// sidebar, so this panel has exactly one thing to show and no switcher.
export function RightPanel({
  inspect,
  studio,
  artifacts,
  toggle,
}: {
  inspect: ReactNode
  studio: ReactNode
  artifacts: ReactNode
  /** Hides the panel; Studio's heading holds it, a preview's header never does. */
  toggle?: ReactNode
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
      {/* Same heading, spacing and placement as the left sidebar's
          "SurfSense" header — Studio's format cards start exactly where
          "New chat" does over there, so they don't need a heading of
          their own. */}
      <header className="shrink-0">
        <ColumnHeader className="justify-between">
          <h2 className="truncate px-1 font-heading text-lg font-medium text-foreground select-none">
            Studio
          </h2>
          {toggle}
        </ColumnHeader>
        <div className="px-3 pt-2">{studio}</div>
      </header>
      <div className="min-h-0 min-w-0 flex-1 overflow-hidden px-3 pb-2">
        {artifacts}
      </div>
    </aside>
  )
}
