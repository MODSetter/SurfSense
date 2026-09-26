import { type ExternalToast, toast } from "sonner"

import { intl } from "@/i18n/intl"

import { openIssueReport } from "./issue-report-state"

/** An error toast that offers Report issue, carrying what it said. */
export function errorToast(title: string, options: ExternalToast = {}) {
  const error =
    typeof options.description === "string"
      ? `${title}: ${options.description}`
      : title
  return toast.error(title, {
    ...options,
    action: {
      label: intl.formatMessage({
        id: "feedback_toast_report_button",
        defaultMessage: "Report issue",
      }),
      onClick: () => openIssueReport({ error }),
    },
  })
}
