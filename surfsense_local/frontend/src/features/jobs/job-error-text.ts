import { translatedStudioError } from "@/features/studio/studio-error-text"
import { intl } from "@/i18n/intl"
import { ApiError } from "@/lib/api"

import type { PackOutcome } from "./api"

// SurfSense's own license server, for a refusal that names no host; Settings ›
// Network shows a mirror's host on its row.
const LICENSE_SERVER_HOST = "api.surfsense.com"

function unexpected() {
  return intl.formatMessage({
    id: "jobs_unexpected_error",
    defaultMessage: "Something went wrong. Try again.",
  })
}

// The backend's own sentence stands for a code this version has no words for.
function sentFrom(error: unknown): string {
  return error instanceof Error && error.message ? error.message : unexpected()
}

function textFor(
  table: Record<string, (error: ApiError) => string>,
  error: unknown
): string | null {
  if (
    !(error instanceof ApiError) ||
    error.code === null ||
    !Object.hasOwn(table, error.code)
  )
    return null
  return table[error.code](error)
}

// English mirrors the download route's refusals (packs/delivery/router.py).
const downloadRefusals: Record<string, (error: ApiError) => string> = {
  // Shown after Cancel at the license server's question, or with no prompt to ask it.
  egress_disabled: (error) =>
    intl.formatMessage(
      {
        id: "jobs_error_egress_disabled",
        defaultMessage:
          "SurfSense didn’t contact its license server, {host}. Try again and choose Allow, or allow it in Settings › Network.",
      },
      {
        host:
          typeof error.detail.host === "string"
            ? error.detail.host
            : LICENSE_SERVER_HOST,
      }
    ),
  license_none: () =>
    intl.formatMessage({
      id: "jobs_error_license_none",
      defaultMessage: "Add a license that includes jobs first.",
    }),
  license_not_active: () =>
    intl.formatMessage({
      id: "jobs_error_license_not_active",
      defaultMessage:
        "Your license has ended, or this computer’s clock is behind, so no job can be downloaded.",
    }),
  license_no_jobs: () =>
    intl.formatMessage({
      id: "jobs_error_license_no_jobs",
      defaultMessage: "Your license includes no jobs to download.",
    }),
}

/** Why a download sent nothing at all, for every job asked for. */
export function downloadFailureText(error: unknown): string {
  return textFor(downloadRefusals, error) ?? sentFrom(error)
}

type OutcomeWords = (job: string, outcome: PackOutcome) => string

// English mirrors the delivery's outcomes (packs/delivery/outcomes.py).
const outcomes: Record<string, OutcomeWords> = {
  // Held back while a run went on, often before the server was asked, so no
  // newer version is known. A deferral names the installed version it kept,
  // so one with none came while no pack here had the job: the pack sent for
  // it was refused (PACK_IN_USE) while a run of another of its jobs went on.
  deferred: (job, { version }) =>
    version === null
      ? intl.formatMessage(
          {
            id: "jobs_row_deferred_pack_status",
            defaultMessage:
              "{job} comes in the same pack as a job whose run was under way, so it waits. SurfSense tries again once the run ends.",
          },
          { job }
        )
      : intl.formatMessage(
          {
            id: "jobs_row_deferred_status",
            defaultMessage:
              "A run of {job} was under way, so any newer version waits. SurfSense checks again once the run ends.",
          },
          { job }
        ),
  job_not_included: (job) =>
    intl.formatMessage(
      {
        id: "jobs_error_job_not_included",
        defaultMessage: "Your license doesn’t include {job}.",
      },
      { job }
    ),
  pack_not_covered: (job) =>
    intl.formatMessage(
      {
        id: "jobs_error_pack_not_covered",
        defaultMessage:
          "{job} comes only in a pack with a job your license doesn’t include, so SurfSense’s license server sent nothing. Contact SurfSense support.",
      },
      { job }
    ),
  license_not_valid: () =>
    intl.formatMessage({
      id: "jobs_error_license_not_valid",
      defaultMessage:
        "SurfSense’s license server didn’t accept this license, so it sent nothing. Check for renewal in Settings › License, or contact SurfSense support.",
    }),
  license_not_found: () =>
    intl.formatMessage({
      id: "jobs_error_license_not_found",
      defaultMessage:
        "SurfSense’s license server has no license with this key.",
    }),
  needs_newer_app: (job) =>
    intl.formatMessage(
      {
        id: "jobs_error_needs_newer_app",
        defaultMessage:
          "{job} needs a newer version of SurfSense. Update the app, then download it again.",
      },
      { job }
    ),
  unknown_job: (job) =>
    intl.formatMessage(
      {
        id: "jobs_error_unknown_job",
        defaultMessage: "SurfSense’s license server has no download for {job}.",
      },
      { job }
    ),
  rate_limited: () =>
    intl.formatMessage({
      id: "jobs_error_rate_limited",
      defaultMessage:
        "Jobs were downloaded too often with this license. Try again in an hour.",
    }),
  unavailable: (job) =>
    intl.formatMessage(
      {
        id: "jobs_error_unavailable",
        defaultMessage:
          "SurfSense’s license server couldn’t send {job}. Try again later.",
      },
      { job }
    ),
  refused: (job) =>
    intl.formatMessage(
      {
        id: "jobs_error_refused",
        defaultMessage:
          "The download of {job} didn’t pass SurfSense’s checks, so it wasn’t installed.",
      },
      { job }
    ),
  // The server sends a pack only when its record of the license lists every
  // job in it, so this computer's license file is the older one.
  license_outdated: (job) =>
    intl.formatMessage(
      {
        id: "jobs_error_license_outdated",
        defaultMessage:
          "Your license has changed on SurfSense’s license server. Check for renewal in Settings › License, then download {job} again.",
      },
      { job }
    ),
  not_written: (job) =>
    intl.formatMessage(
      {
        id: "jobs_error_not_written",
        defaultMessage:
          "SurfSense couldn’t save {job} on this computer. Check that the disk has room, then try again.",
      },
      { job }
    ),
}

/** What one job's download came to, named by its row; null when it is
 *  installed or already current, which needs no line. */
export function outcomeText(outcome: PackOutcome, job: string): string | null {
  if (outcome.outcome === "installed" || outcome.outcome === "current")
    return null
  return Object.hasOwn(outcomes, outcome.outcome)
    ? outcomes[outcome.outcome](job, outcome)
    : outcome.message || unexpected()
}

const notAPack = () =>
  intl.formatMessage({
    id: "jobs_error_not_a_pack",
    defaultMessage:
      "This file isn’t a SurfSense job pack. Choose the job pack’s .zip file.",
  })

const tampered = () =>
  intl.formatMessage({
    id: "jobs_error_pack_tampered",
    defaultMessage:
      "This job pack was changed after SurfSense signed it, or SurfSense didn’t sign it, so it can’t be used.",
  })

/** Said before sending a file past the backend's cap. */
export function packTooLargeText(): string {
  return intl.formatMessage({
    id: "jobs_error_pack_too_large",
    defaultMessage: "This file is larger than a job pack can be (50 MB).",
  })
}

// English mirrors the import route's refusals (packs/delivery/router.py).
const importRefusals: Record<string, () => string> = {
  NOT_A_PACK: notAPack,
  BAD_MANIFEST: notAPack,
  BAD_PATH: notAPack,
  PACK_NOT_SIGNED: tampered,
  PACK_BAD_SIGNATURE: tampered,
  PACK_FILE_UNLISTED: tampered,
  PACK_FILE_MISSING: tampered,
  PACK_FILE_CHANGED: tampered,
  // A file past the cap is refused before it is sent, so this one is a zip
  // holding more files, or more once extracted, than a job pack can.
  PACK_TOO_LARGE: notAPack,
  NEEDS_NEWER_APP: () =>
    intl.formatMessage({
      id: "jobs_error_pack_needs_newer_app",
      defaultMessage:
        "This job pack needs a newer version of SurfSense. Update the app, then import it again.",
    }),
  PACK_OLDER: () =>
    intl.formatMessage({
      id: "jobs_error_pack_older",
      defaultMessage: "A newer version of this job is already installed.",
    }),
  PACK_IN_USE: () =>
    intl.formatMessage({
      id: "jobs_error_pack_in_use",
      defaultMessage:
        "A run of this job is still going. Import the pack once it finishes.",
    }),
  PACK_VERSION_TAKEN: () =>
    intl.formatMessage({
      id: "jobs_error_pack_version_taken",
      defaultMessage:
        "A different copy of this version is already installed. Import a newer version instead.",
    }),
  PACK_NOT_WRITTEN: () =>
    intl.formatMessage({
      id: "jobs_error_pack_not_written",
      defaultMessage:
        "SurfSense couldn’t save the pack on this computer. Check that the disk has room, then try again.",
    }),
}

/** Why a pack file the user picked was not installed. */
export function importErrorText(error: unknown): string {
  return textFor(importRefusals, error) ?? sentFrom(error)
}

const jobsRefusals: Record<string, () => string> = {
  // Its settings were asked for after its pack left this computer.
  NOT_FOUND: () =>
    intl.formatMessage({
      id: "jobs_error_job_missing",
      defaultMessage: "This job is no longer on this computer.",
    }),
}

/** A refused run, settings save, confirmation, cancel or run again. A run's
 *  refusal (JOB_RUN_REFUSED) and the pack's own complaints are the backend's
 *  sentences, shown as sent. */
export function jobsErrorText(error: unknown): string {
  return (
    textFor(jobsRefusals, error) ??
    translatedStudioError(error) ??
    sentFrom(error)
  )
}
