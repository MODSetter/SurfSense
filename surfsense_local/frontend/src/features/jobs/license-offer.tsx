import type { ReactNode } from "react"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { InformationCircleIcon } from "@/components/ui/icons"
import { Spinner } from "@/components/ui/spinner"
import { ExternalLink } from "@/features/about/external-link"
import { useAppDetails } from "@/features/about/use-app-details"
import type { LicenseStatus } from "@/features/license/api"
import { translatedLicenseError } from "@/features/license/license-error-text"
import { pricingUrl } from "@/features/license/license-links"
import { planName } from "@/features/license/plan-name"
import { TrialButton } from "@/features/license/trial-button"
import { useLicenseRefresh } from "@/features/license/use-license-refresh"
import { intl } from "@/i18n/intl"

import type { JobRow } from "./job-rows"
import { leadingLock, type LicenseLock } from "./license-lock"

// The alert's description sets the type and spaces its paragraphs.
function Sentence({ children }: { children: ReactNode }) {
  return <p>{children}</p>
}

function Actions({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
      {children}
    </div>
  )
}

function TrialLink() {
  return (
    <TrialButton
      surface="jobs_trial"
      size="sm"
      label={intl.formatMessage({
        id: "jobs_row_trial_link",
        defaultMessage: "Start 14-day trial",
      })}
    />
  )
}

function PricingLink({ version }: { version: string | undefined }) {
  return (
    <ExternalLink href={pricingUrl("jobs_pricing", version)}>
      {intl.formatMessage({
        id: "jobs_row_pricing_link",
        defaultMessage: "See pricing",
      })}
    </ExternalLink>
  )
}

function LicenseButton({
  replace,
  onOpenLicense,
}: {
  replace: boolean
  onOpenLicense: () => void
}) {
  return (
    <Button type="button" variant="ghost" size="sm" onClick={onOpenLicense}>
      {replace
        ? intl.formatMessage({
            id: "jobs_row_replace_license_button",
            defaultMessage: "Replace license",
          })
        : intl.formatMessage({
            id: "jobs_row_add_license_button",
            defaultMessage: "Add license",
          })}
    </Button>
  )
}

/** A license that may have been renewed, or moved to Business, on the same
 *  key: the check fetches its newest file, which publishing then acts on. */
function RenewalOffer({
  sentence,
  version,
}: {
  sentence: string
  version: string | undefined
}) {
  const refresh = useLicenseRefresh()
  const checked = refresh.data
  return (
    <>
      <Sentence>{sentence}</Sentence>
      <Actions>
        <Button
          type="button"
          variant="default"
          size="sm"
          disabled={refresh.isPending}
          onClick={() => refresh.mutate()}
        >
          {refresh.isPending ? <Spinner data-icon="inline-start" /> : null}
          {intl.formatMessage({
            id: "jobs_row_renewal_button",
            defaultMessage: "Check for renewal",
          })}
        </Button>
        <PricingLink version={version} />
      </Actions>
      {refresh.error ? (
        <p role="alert" className="text-sm text-pretty text-destructive">
          {translatedLicenseError(refresh.error)}
        </p>
      ) : checked ? (
        <p role="status" className="text-sm text-muted-foreground tabular-nums">
          {checked.renewed && checked.status.expiry
            ? intl.formatMessage(
                {
                  id: "jobs_row_renewed_status",
                  defaultMessage: "Renewed until {date, date, ::yyyyMMMd}",
                },
                { date: new Date(checked.status.expiry) }
              )
            : intl.formatMessage({
                id: "jobs_row_not_renewed_status",
                defaultMessage: "No renewal yet",
              })}
        </p>
      ) : null}
    </>
  )
}

function OfferBody({
  lock,
  count,
  license,
  onOpenLicense,
}: {
  lock: LicenseLock
  // How many jobs it holds; the rows it names carry a mark.
  count: number
  license: LicenseStatus
  onOpenLicense: () => void
}) {
  const version = useAppDetails().data?.version
  switch (lock) {
    case "locked_none":
      return (
        <>
          <Sentence>
            {intl.formatMessage({
              id: "jobs_offer_locked_none_body",
              defaultMessage:
                "Jobs come with a SurfSense Business license. Try it free for 14 days.",
            })}
          </Sentence>
          <Actions>
            <TrialLink />
            <PricingLink version={version} />
            <LicenseButton replace={false} onOpenLicense={onOpenLicense} />
          </Actions>
        </>
      )
    case "locked_trial":
      return (
        <>
          <Sentence>
            {intl.formatMessage(
              {
                id: "jobs_offer_locked_trial_body",
                defaultMessage:
                  "Your license doesn’t include {count, plural, one {the job marked Business} other {the jobs marked Business}}. Jobs come with a Business license, which you can try free for 14 days.",
              },
              { count }
            )}
          </Sentence>
          <Actions>
            <TrialLink />
            <PricingLink version={version} />
            <LicenseButton replace onOpenLicense={onOpenLicense} />
          </Actions>
        </>
      )
    case "locked_paid":
      return (
        <RenewalOffer
          version={version}
          sentence={intl.formatMessage(
            {
              id: "jobs_offer_locked_paid_body",
              defaultMessage:
                "Your {plan} license doesn’t include {count, plural, one {the job marked Business} other {the jobs marked Business}}: jobs come with Business. If your license has moved to Business, Check for renewal fetches its new file.",
            },
            { plan: planName(license), count }
          )}
        />
      )
    case "trial_ended":
      return (
        <>
          <Sentence>
            {intl.formatMessage({
              id: "jobs_offer_trial_ended_body",
              defaultMessage:
                "Your 14-day trial has ended. To keep running jobs, buy a Business license, then replace the trial’s license with the one we email you.",
            })}
          </Sentence>
          <Actions>
            <PricingLink version={version} />
            <LicenseButton replace onOpenLicense={onOpenLicense} />
          </Actions>
        </>
      )
    case "expired":
      return (
        <RenewalOffer
          version={version}
          sentence={intl.formatMessage(
            {
              id: "jobs_offer_expired_body",
              defaultMessage:
                "Your license has ended, so {count, plural, one {the job marked Locked} other {the jobs marked Locked}} can’t run. If it was renewed, Check for renewal fetches the new file.",
            },
            { count }
          )}
        />
      )
    case "clock":
      return (
        <Sentence>
          {intl.formatMessage(
            {
              id: "jobs_offer_clock_body",
              defaultMessage:
                "This computer’s clock is behind the last time SurfSense ran. Set the clock right to run {count, plural, one {the job marked Locked} other {the jobs marked Locked}}.",
            },
            { count }
          )}
        </Sentence>
      )
  }
}

/**
 * What the license would need, said once above the jobs instead of on each
 * one: the lock to fix first, while each locked row carries its mark.
 */
export function LicenseOffer({
  rows,
  license,
  onOpenLicense,
}: {
  rows: readonly JobRow[]
  license: LicenseStatus
  onOpenLicense: () => void
}) {
  const leading = leadingLock(rows)
  if (!leading) return null
  return (
    <Alert
      variant="secondary"
      // An offer, not an error: a named region, so opening Jobs announces nothing.
      role="region"
      aria-label={intl.formatMessage({
        id: "jobs_offer_aria",
        defaultMessage: "License",
      })}
    >
      <InformationCircleIcon aria-hidden />
      <AlertDescription>
        <OfferBody
          lock={leading.lock}
          count={leading.count}
          license={license}
          onOpenLicense={onOpenLicense}
        />
      </AlertDescription>
    </Alert>
  )
}
