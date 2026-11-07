import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"

import { jobsErrorText } from "../job-error-text"

/** Starts the run the form holds, and says why the backend refused one. */
export function StartRunButton({
  error,
  busy,
  disabled,
  onStart,
}: {
  error: unknown
  busy: boolean
  disabled: boolean
  onStart: () => void
}) {
  return (
    <>
      {error ? (
        <p role="alert" className="text-sm text-pretty text-destructive">
          {jobsErrorText(error)}
        </p>
      ) : null}
      <div className="flex justify-end">
        <Button type="button" disabled={disabled} onClick={onStart}>
          {busy ? <Spinner data-icon="inline-start" /> : null}
          {busy
            ? intl.formatMessage({
                id: "jobs_run_starting_status",
                defaultMessage: "Starting…",
              })
            : intl.formatMessage({
                id: "jobs_run_start_button",
                defaultMessage: "Start",
              })}
        </Button>
      </div>
    </>
  )
}
