import { intl } from "@/i18n/intl"

import { AllJobsButton } from "../all-jobs-button"

/** A run form's way back to every job, above the job it runs. */
export function RunFormHeader({
  title,
  busy,
  onBack,
}: {
  title: string
  busy: boolean
  onBack: () => void
}) {
  return (
    <div className="flex flex-col gap-1">
      <AllJobsButton onClick={onBack} disabled={busy} />
      <h3 className="text-base font-medium text-balance">
        {intl.formatMessage(
          { id: "jobs_run_title", defaultMessage: "Run {job}" },
          { job: title }
        )}
      </h3>
    </div>
  )
}
