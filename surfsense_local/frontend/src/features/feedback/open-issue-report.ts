/** What a caller knows when it sends the user to Report issue. */
export type ReportContext = { error?: string }

// Set while the dialog is mounted, as `registerAskHandler` is for the egress prompt.
let open: ((context: ReportContext) => void) | null = null

export function setOpenHandler(handler: typeof open): void {
  open = handler
}

// Does nothing without the dialog, as in a test that renders one screen.
export function openIssueReport(context: ReportContext = {}): void {
  open?.(context)
}
