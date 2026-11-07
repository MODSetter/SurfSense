import { jobName } from "@/features/license/job-names"
import { intl } from "@/i18n/intl"

import type { PackInfo } from "./api"
import { WORKBOOK_ROWS } from "./runners"

/** A job this version of SurfSense sells, shown before its pack is on this computer. */
export type CatalogJob = {
  entitlement: string
  // The sold pack's job key; a run sends the installed job's own key.
  job: string
  name: () => string
  description: () => string
}

export const JOB_CATALOG: readonly CatalogJob[] = [
  {
    entitlement: "JOB_QUESTIONNAIRE",
    job: "security-questionnaire",
    // The license's own name for the code, so a job has one name across the app.
    name: () => jobName("JOB_QUESTIONNAIRE"),
    description: () =>
      intl.formatMessage({
        id: "jobs_catalog_questionnaire_body",
        defaultMessage:
          "Fills in a security questionnaire workbook (.xlsx) from your firm’s own policies, with the source of each answer. What it can’t back with a quote is left for a person to check.",
      }),
  },
  {
    entitlement: "JOB_CONTRACT_REDLINE",
    job: "contract-redline",
    name: () => jobName("JOB_CONTRACT_REDLINE"),
    description: () =>
      intl.formatMessage({
        id: "jobs_catalog_contract_redline_body",
        defaultMessage:
          "Reviews a contract you received (.docx) against your firm’s own playbook, and marks up a copy with tracked changes and comments. Where your playbook takes no position, the contract is left as it is.",
      }),
  },
]

function catalogEntry(entitlement: string | null) {
  return JOB_CATALOG.find((entry) => entry.entitlement === entitlement)
}

/** The catalog's name for a code, else the pack's own, else the code as sent. */
export function jobTitle(
  entitlement: string | null,
  packName?: string
): string {
  const entry = catalogEntry(entitlement)
  if (entry) return entry.name()
  if (packName) return packName
  return entitlement === null ? "" : jobName(entitlement)
}

/** A run's job by its key: named as its row is, else by the key as sent. */
export function jobTitleOfKey(
  key: string,
  packs: readonly PackInfo[] | undefined
): string {
  const sold = JOB_CATALOG.find((entry) => entry.job === key)
  if (sold) return sold.name()
  for (const pack of packs ?? []) {
    const job = pack.jobs.find((each) => each.key === key)
    if (job) return jobTitle(job.entitlement, job.name)
  }
  return key
}

/** A job's runner by its key: the installed job's, else a workbook's, the one
 *  runner before jobs named theirs. */
export function jobRunnerOfKey(
  key: string,
  packs?: readonly PackInfo[]
): string {
  for (const pack of packs ?? []) {
    const job = pack.jobs.find((each) => each.key === key)
    if (job) return job.runner
  }
  return WORKBOOK_ROWS
}
