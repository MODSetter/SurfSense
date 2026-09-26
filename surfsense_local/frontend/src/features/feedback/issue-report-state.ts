import { useEffect, useSyncExternalStore } from "react"

/** What a caller knows when it sends the user to Report issue. */
export type ReportContext = { error?: string }

type IssueReport = {
  open: boolean
  context: ReportContext
  // Outlives the dialog, so a stray Escape does not lose a half-written report.
  description: string
  includeLog: boolean
  copyFailed: boolean
}

const CLOSED: IssueReport = {
  open: false,
  context: {},
  description: "",
  includeLog: true,
  copyFailed: false,
}

// Outside the dialog, which remounts wherever the innermost open dialog is.
let report = CLOSED
let dialogs = 0
const listeners = new Set<() => void>()

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => void listeners.delete(listener)
}

export function updateIssueReport(patch: Partial<IssueReport>): void {
  report = { ...report, ...patch }
  listeners.forEach((listener) => listener())
}

export function openIssueReport(context: ReportContext = {}): void {
  updateIssueReport({ open: true, context, copyFailed: false })
}

// Lives as long as a report dialog is mounted, as the dialog's own state did.
export function useIssueReport(): IssueReport {
  useEffect(() => {
    dialogs += 1
    return () => {
      dialogs -= 1
      // After the commit, so moving to another dialog is not an unmount.
      queueMicrotask(() => {
        if (dialogs === 0) report = CLOSED
      })
    }
  }, [])
  return useSyncExternalStore(subscribe, () => report)
}
