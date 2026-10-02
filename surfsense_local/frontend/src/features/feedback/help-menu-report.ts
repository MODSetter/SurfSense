import { useEffect, useRef } from "react"

// Who answers Help › Report Issue… in the macOS menu bar.
//
// Claimed by: the dashboard (`dashboard-page.tsx`), which opens Settings ›
// Report issue. Unclaimed, as on loading, onboarding and the startup error
// screen where no Settings dialog exists, the menu opens IssueReportDialog.
// Only one claimant at a time; the latest mount wins.
let claimant: (() => void) | null = null

export function helpMenuReportClaimant(): (() => void) | null {
  return claimant
}

export function useHelpMenuReport(onReport: () => void): void {
  // Read at click time, so a re-render's new closure needs no re-claim.
  const latest = useRef(onReport)
  useEffect(() => {
    latest.current = onReport
  })
  useEffect(() => {
    const claim = () => latest.current()
    claimant = claim
    return () => {
      if (claimant === claim) claimant = null
    }
  }, [])
}
