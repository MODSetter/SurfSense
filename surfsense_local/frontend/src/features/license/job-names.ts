import { intl } from "@/i18n/intl"

// Keygen entitlement codes from the license's metadata.jobs. A code this
// version does not know yet is shown as sent rather than hidden.
const jobNames: Record<string, () => string> = {
  JOB_QUESTIONNAIRE: () =>
    intl.formatMessage({
      id: "license_jobs_questionnaire_label",
      defaultMessage: "Security questionnaire",
    }),
}

export function jobName(code: string): string {
  return Object.hasOwn(jobNames, code) ? jobNames[code]() : code
}
