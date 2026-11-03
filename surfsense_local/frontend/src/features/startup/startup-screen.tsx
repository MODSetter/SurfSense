import { DashboardShell } from "@/features/dashboard/dashboard-shell"
import { intl } from "@/i18n/intl"

import { StartupFrame } from "./startup-frame"

/**
 * What shows while startup waits on the API: the dashboard's frame when the
 * dashboard is expected next, else the window's plain background, so
 * onboarding never opens over a glimpse of the dashboard.
 */
export function StartupScreen({ frame }: { frame: boolean }) {
  const label = intl.formatMessage({
    id: "app_bootstrap_loader_aria",
    defaultMessage: "Starting SurfSense",
  })
  return (
    // Busy, not a status region: the frame holds a box to type in.
    <DashboardShell aria-busy="true" aria-label={label}>
      <p role="status" className="sr-only">
        {label}
      </p>
      {frame ? <StartupFrame /> : null}
    </DashboardShell>
  )
}
