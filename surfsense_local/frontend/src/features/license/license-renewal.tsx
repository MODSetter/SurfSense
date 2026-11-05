import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"

import { translatedLicenseError } from "./license-error-text"
import type { LicenseRefresh } from "./use-license-refresh"

/**
 * Business renews on the same key, so a renewal is a newer file for this
 * license to fetch, not a new one to add; offline, the emailed file still is.
 */
export function LicenseRenewal({
  refresh,
  disabled,
}: {
  refresh: LicenseRefresh
  disabled: boolean
}) {
  const checked = refresh.data
  return (
    <div className="mt-8 flex items-start justify-between gap-8">
      <div className="flex flex-col gap-1">
        <h3 className="text-sm font-medium text-balance">
          {intl.formatMessage({
            id: "license_renewal_title",
            defaultMessage: "Renewal",
          })}
        </h3>
        <p className="text-sm text-pretty text-muted-foreground">
          {intl.formatMessage({
            id: "license_renewal_body",
            defaultMessage:
              "Checking sends your license key to SurfSense’s license server and replaces the file on this device with the latest one.",
          })}
        </p>
        {refresh.error ? (
          <p role="alert" className="text-sm text-destructive">
            {translatedLicenseError(refresh.error)}
          </p>
        ) : checked ? (
          <p
            role="status"
            className="text-sm text-muted-foreground tabular-nums"
          >
            {checked.renewed && checked.status.expiry
              ? intl.formatMessage(
                  {
                    id: "license_renewal_renewed_status",
                    defaultMessage: "Renewed until {date, date, ::yyyyMMMd}",
                  },
                  { date: new Date(checked.status.expiry) }
                )
              : intl.formatMessage({
                  id: "license_renewal_unchanged_status",
                  defaultMessage: "No renewal yet",
                })}
          </p>
        ) : null}
      </div>
      <Button
        type="button"
        variant="outline"
        disabled={disabled || refresh.isPending}
        onClick={() => refresh.mutate()}
      >
        {refresh.isPending ? <Spinner data-icon="inline-start" /> : null}
        {intl.formatMessage({
          id: "license_renewal_check_button",
          defaultMessage: "Check for renewal",
        })}
      </Button>
    </div>
  )
}
