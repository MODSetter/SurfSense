import { LockIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

import { needsBusiness, type LicenseLock } from "./license-lock"

/** A locked row's mark, which the license's offer above the jobs explains. */
export function LicenseLockBadge({ lock }: { lock: LicenseLock }) {
  return (
    <span className="inline-flex shrink-0 items-center gap-1 rounded-md bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
      <LockIcon aria-hidden className="size-3" />
      {needsBusiness(lock)
        ? intl.formatMessage({
            id: "jobs_row_business_label",
            defaultMessage: "Business",
          })
        : intl.formatMessage({
            id: "jobs_row_locked_label",
            defaultMessage: "Locked",
          })}
    </span>
  )
}
