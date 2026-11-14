import type { LicenseStatus } from "@/features/license/api"
import { jobName } from "@/features/license/job-names"

import type { JobInfo, LockedCode, PackInfo } from "./api"
import { JOB_CATALOG } from "./catalog"

/**
 * What a row offers. A paid license that is not Business's trial (Individual,
 * Team, a hand-issued Business) is never offered a trial: the trial's file
 * would replace its one license.
 */
export type JobRowKind =
  | "available"
  | "not_downloaded"
  | "locked_none"
  | "locked_trial"
  | "locked_paid"
  | "trial_ended"
  | "expired"
  | "clock"
  | "no_entitlement"

export type JobRow = {
  // The entitlement code, or `job:<key>` for a job without one.
  key: string
  entitlement: string | null
  // The installed job's key, which a run sends; null while none is installed.
  job: string | null
  name: string
  description: string | null
  version: string | null
  // Every installed pack's version with a job for the row's code, the one
  // shown among them: a check a run held back names the newest.
  versions: string[]
  kind: JobRowKind
}

export type InstalledJob = { job: JobInfo; version: string }

const isTrial = (license: LicenseStatus) => license.plan === "trial"

function lockedKind(code: LockedCode, license: LicenseStatus): JobRowKind {
  switch (code) {
    case "none":
      return "locked_none"
    case "not_included":
      return isTrial(license) ? "locked_trial" : "locked_paid"
    case "expired":
      return isTrial(license) ? "trial_ended" : "expired"
    case "clock":
      return "clock"
    case "no_entitlement":
      return "no_entitlement"
  }
}

// In the backend's order (access.py): no license, the code not carried, ended, the clock.
function licenseKind(code: string, license: LicenseStatus): JobRowKind {
  if (license.state === "none") return "locked_none"
  if (!license.jobs.includes(code))
    return isTrial(license) ? "locked_trial" : "locked_paid"
  if (license.state === "license_expired")
    return isTrial(license) ? "trial_ended" : "expired"
  if (license.state === "clock_untrusted") return "clock"
  return "not_downloaded"
}

function kindOf(
  installed: InstalledJob | undefined,
  code: string | null,
  license: LicenseStatus
): JobRowKind {
  if (installed?.job.unlocked) return "available"
  if (installed?.job.locked_code)
    return lockedKind(installed.job.locked_code, license)
  if (code === null) return "no_entitlement"
  return licenseKind(code, license)
}

// The unlocked one runs, so it is the one shown.
function chosen(candidates: readonly InstalledJob[]): InstalledJob | undefined {
  return candidates.find((each) => each.job.unlocked) ?? candidates[0]
}

function installedJobs(packs: readonly PackInfo[]): InstalledJob[] {
  return packs.flatMap((pack) =>
    pack.jobs.map((job) => ({ job, version: pack.version }))
  )
}

function withCode(
  installed: readonly InstalledJob[],
  code: string
): InstalledJob[] {
  return installed.filter((each) => each.job.entitlement === code)
}

/** The installed job a code's row stands for: the unlocked one, else the first. */
export function installedJobFor(
  packs: readonly PackInfo[],
  code: string
): InstalledJob | undefined {
  return chosen(withCode(installedJobs(packs), code))
}

/** The version of every installed pack with a job for a code. */
export function installedVersionsFor(
  packs: readonly PackInfo[],
  code: string
): string[] {
  return withCode(installedJobs(packs), code).map((each) => each.version)
}

function row(
  key: string,
  code: string | null,
  name: string,
  description: string | null,
  candidates: readonly InstalledJob[],
  license: LicenseStatus
): JobRow {
  const installed = chosen(candidates)
  return {
    key,
    entitlement: code,
    job: installed?.job.key ?? null,
    name,
    description,
    version: installed?.version ?? null,
    versions: candidates.map((each) => each.version),
    kind: kindOf(installed, code, license),
  }
}

/** The catalog's jobs in order, then installed jobs it does not sell by
 *  name, then the license's codes neither covers. */
export function jobRows(
  packs: readonly PackInfo[],
  license: LicenseStatus
): JobRow[] {
  const installed = installedJobs(packs)
  const sold = new Set(JOB_CATALOG.map((entry) => entry.entitlement))

  const catalogRows = JOB_CATALOG.map((entry) =>
    row(
      entry.entitlement,
      entry.entitlement,
      entry.name(),
      entry.description(),
      withCode(installed, entry.entitlement),
      license
    )
  )

  const unsold = new Map<string, InstalledJob[]>()
  const uncoded: InstalledJob[] = []
  for (const each of installed) {
    const code = each.job.entitlement
    if (code === null) uncoded.push(each)
    else if (!sold.has(code))
      unsold.set(code, [...(unsold.get(code) ?? []), each])
  }
  const installedRows = [
    ...[...unsold].map(([code, candidates]) => {
      const shown = chosen(candidates)!
      return row(
        code,
        code,
        shown.job.name,
        shown.job.description || null,
        candidates,
        license
      )
    }),
    ...uncoded.map((each) =>
      row(
        `job:${each.job.key}`,
        null,
        each.job.name,
        each.job.description || null,
        [each],
        license
      )
    ),
  ].toSorted((a, b) => a.name.localeCompare(b.name))

  const listed = new Set([...sold, ...unsold.keys()])
  const licenseRows = [...new Set(license.jobs)]
    .filter((code) => !listed.has(code))
    .map((code) => row(code, code, jobName(code), null, [], license))

  return [...catalogRows, ...installedRows, ...licenseRows]
}
