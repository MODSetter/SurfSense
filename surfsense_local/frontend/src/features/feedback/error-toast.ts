import { type ExternalToast, toast } from "sonner"

import { intl } from "@/i18n/intl"

import { openIssueReport } from "./issue-report-state"

type ErrorToastOptions = ExternalToast & { reportError?: string }

/**
 * An error toast that offers Report issue with its diagnostic context. Always
 * opens IssueReportDialog, never Settings: toasts also fire during onboarding.
 */
export function errorToast(title: string, options: ErrorToastOptions = {}) {
  const { reportError, ...toastOptions } = options
  const error =
    reportError ??
    (typeof toastOptions.description === "string"
      ? `${title}: ${toastOptions.description}`
      : title)
  return toast.error(title, {
    ...toastOptions,
    action: {
      label: intl.formatMessage({
        id: "feedback_toast_report_button",
        defaultMessage: "Report issue",
      }),
      onClick: () => openIssueReport({ error }),
    },
  })
}
