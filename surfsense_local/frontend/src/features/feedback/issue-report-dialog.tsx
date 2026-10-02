import { useEffect, useRef } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { intl } from "@/i18n/intl"

import { helpMenuReportClaimant } from "./help-menu-report"
import { IssueReportForm } from "./issue-report-form"
import {
  openIssueReport,
  updateIssueReport,
  useIssueReport,
} from "./issue-report-state"

// An app dialog (`AppDialogs`), so it opens over whatever dialog is open.
//
// Opened by: the Report issue button on error toasts (`error-toast.ts`), the
// sidecar crash notice (`sidecar-crash-reporter.tsx`), and Help › Report
// Issue… only while nothing claims it (`help-menu-report.ts`). These fire on
// any screen, including onboarding, where Settings does not exist. Settings ›
// Report issue (`report-issue-settings.tsx`) shows the same form inline.
export function IssueReportDialog() {
  const descriptionRef = useRef<HTMLTextAreaElement>(null)
  const { open } = useIssueReport()
  const setOpen = (open: boolean) => updateIssueReport({ open })

  useEffect(
    () =>
      window.surfsense?.help?.onReportIssue(() => {
        const claimant = helpMenuReportClaimant()
        if (claimant) claimant()
        else openIssueReport()
      }),
    []
  )

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent
        className="max-h-[calc(100dvh-2rem)] overflow-y-auto select-none sm:max-w-3xl"
        initialFocus={descriptionRef}
      >
        <IssueReportForm
          active={open}
          descriptionRef={descriptionRef}
          header={
            <DialogHeader>
              <DialogTitle>
                {intl.formatMessage({
                  id: "feedback_dialog_title",
                  defaultMessage: "Report an issue",
                })}
              </DialogTitle>
              <DialogDescription className="text-pretty">
                {intl.formatMessage({
                  id: "feedback_dialog_body",
                  defaultMessage:
                    "Describe what went wrong, and GitHub opens with your report filled in for the SurfSense team.",
                })}
              </DialogDescription>
            </DialogHeader>
          }
          footer={(submit) => (
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setOpen(false)}
              >
                {intl.formatMessage({
                  id: "feedback_form_cancel_button",
                  defaultMessage: "Cancel",
                })}
              </Button>
              {submit}
            </DialogFooter>
          )}
        />
      </DialogContent>
    </Dialog>
  )
}
