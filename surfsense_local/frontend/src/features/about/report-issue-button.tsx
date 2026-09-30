import { openIssueReport } from "@/features/feedback/issue-report-state"
import { intl } from "@/i18n/intl"

// Styled as the links beside it, but opens the dialog, which carries the session
// log and the system details.
export function ReportIssueButton() {
  return (
    <button
      type="button"
      onClick={() => openIssueReport()}
      className="inline-flex w-fit cursor-pointer items-center gap-1.5 text-sm text-muted-foreground underline-offset-3 transition-colors hover:text-foreground hover:underline"
    >
      {intl.formatMessage({
        id: "about_report_issue_button",
        defaultMessage: "Report an issue",
      })}
    </button>
  )
}
