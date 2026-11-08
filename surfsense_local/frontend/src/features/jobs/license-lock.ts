import type { JobRow, JobRowKind } from "./job-rows"

/** Locks the license itself decides, so one offer stands for every job they hold. */
export type LicenseLock = Extract<
  JobRowKind,
  | "clock"
  | "expired"
  | "trial_ended"
  | "locked_none"
  | "locked_trial"
  | "locked_paid"
>

// The one to fix first leads: a clock or an ended license stops every job,
// and a job the license lacks still needs a working license.
const BY_URGENCY: readonly LicenseLock[] = [
  "clock",
  "expired",
  "trial_ended",
  "locked_none",
  "locked_trial",
  "locked_paid",
]

export function isLicenseLock(kind: JobRowKind): kind is LicenseLock {
  return (BY_URGENCY as readonly JobRowKind[]).includes(kind)
}

/** The license's one offer for these rows, and how many jobs it names; null when none is locked. */
export function leadingLock(
  rows: readonly JobRow[]
): { lock: LicenseLock; count: number } | null {
  for (const lock of BY_URGENCY) {
    const count = rows.filter((row) => row.kind === lock).length
    if (count > 0) return { lock, count }
  }
  return null
}

export function needsBusiness(lock: LicenseLock) {
  return (
    lock === "locked_none" || lock === "locked_trial" || lock === "locked_paid"
  )
}
