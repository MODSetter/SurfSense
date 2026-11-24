import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"

import { downloadFailureText, outcomeText } from "../job-error-text"

import type { Delivery } from "./download-job-packs"

function downloading(place: "row" | "license") {
  return place === "row"
    ? intl.formatMessage({
        id: "jobs_row_downloading_status",
        defaultMessage: "Downloading…",
      })
    : intl.formatMessage({
        id: "jobs_license_downloading_status",
        defaultMessage: "Downloading…",
      })
}

// Settings › License's line for a deferral; a row's comes from outcomeText.
// With no version, no pack here had the job: the pack that adds it waited on
// a run of another of its jobs.
function licenseDeferredText(version: string | null, job: string) {
  return version === null
    ? intl.formatMessage(
        {
          id: "jobs_license_deferred_pack_status",
          defaultMessage:
            "{job} comes in the same pack as a job whose run was under way, so it waits until the run ends.",
        },
        { job }
      )
    : intl.formatMessage(
        {
          id: "jobs_license_deferred_status",
          defaultMessage:
            "A run of {job} was under way, so any newer version waits until the run ends.",
        },
        { job }
      )
}

/**
 * What a job's last download came to, where its job is listed. A failure is
 * said only where Download can be pressed again; installed and current need
 * no line. A check a run held back is said only while the version it kept is
 * still here, or, when it kept none, while none is: the check made once the
 * run ends may put another in place.
 */
export function DeliveryLine({
  delivery,
  job,
  installedVersions,
  place,
  showFailure,
}: {
  delivery: Delivery | undefined
  // The job's name, as its row or line shows it.
  job: string
  // Every installed pack's version with a job for its code, empty while none
  // is: a check a run held back names the newest, not always the one shown.
  installedVersions: readonly string[]
  place: "row" | "license"
  showFailure: boolean
}) {
  if (!delivery) return null
  if (delivery.phase === "downloading")
    return (
      <p
        role="status"
        className="flex items-center gap-1.5 text-sm text-muted-foreground"
      >
        <Spinner aria-hidden="true" className="size-3.5" />
        {downloading(place)}
      </p>
    )
  if (delivery.phase === "failed")
    return showFailure ? (
      <p role="alert" className="text-sm text-pretty text-destructive">
        {downloadFailureText(delivery.error)}
      </p>
    ) : null
  const { outcome } = delivery
  if (outcome.outcome === "deferred") {
    // A deferral names the installed version it kept, so one with none came
    // while no pack here had the job, and is said only while none has it.
    const kept =
      outcome.version === null
        ? installedVersions.length === 0
        : installedVersions.includes(outcome.version)
    if (!kept) return null
    return (
      <p role="status" className="text-sm text-pretty text-muted-foreground">
        {place === "row"
          ? outcomeText(outcome, job)
          : licenseDeferredText(outcome.version, job)}
      </p>
    )
  }
  const text = outcomeText(outcome, job)
  return text ? (
    <p role="alert" className="text-sm text-pretty text-destructive">
      {text}
    </p>
  ) : null
}
