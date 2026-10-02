import { Troubleshooting } from "@/features/about/troubleshooting"
import { useAppDetails } from "@/features/about/use-app-details"
import { SettingsSection } from "@/features/settings/settings-section"
import { intl } from "@/i18n/intl"

import { IssueReportForm } from "./issue-report-form"

// Settings › Report issue. Reached from the nav and, on the dashboard, from
// Help › Report Issue… (`help-menu-report.ts`). Toasts and the crash notice
// open IssueReportDialog instead, since they fire where Settings does not exist.
export function ReportIssueSettings() {
  const details = useAppDetails()

  return (
    <SettingsSection
      title={intl.formatMessage({
        id: "feedback_settings_title",
        defaultMessage: "Report issue",
      })}
      description={intl.formatMessage({
        id: "feedback_settings_body",
        defaultMessage:
          "Describe what went wrong, and GitHub opens with your report filled in for the SurfSense team.",
      })}
    >
      <IssueReportForm active />
      {details.data ? <Troubleshooting details={details.data} /> : null}
    </SettingsSection>
  )
}
