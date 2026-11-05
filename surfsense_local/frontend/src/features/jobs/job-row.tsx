import type { ReactNode } from "react"
import { useQueryClient } from "@tanstack/react-query"

import { Button } from "@/components/ui/button"
import { Download01Icon } from "@/components/ui/icons"
import { Spinner } from "@/components/ui/spinner"
import { ExternalLink } from "@/features/about/external-link"
import { useAppDetails } from "@/features/about/use-app-details"
import type { LicenseStatus } from "@/features/license/api"
import { translatedLicenseError } from "@/features/license/license-error-text"
import { pricingUrl, supportUrl } from "@/features/license/license-links"
import { planName } from "@/features/license/plan-name"
import { TrialButton } from "@/features/license/trial-button"
import { useLicenseRefresh } from "@/features/license/use-license-refresh"
import { intl } from "@/i18n/intl"

import type { JobRow } from "./job-rows"
import { DeliveryLine } from "./packs/delivery-line"
import { downloadJobPacks, type Delivery } from "./packs/download-job-packs"
import { ImportPackButton } from "./packs/import-pack-button"

function Sentence({ children }: { children: ReactNode }) {
  return <p className="text-sm text-pretty">{children}</p>
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
    <Button type="button" variant="outline" size="sm" onClick={onOpenLicense}>
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
          variant="outline"
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

function DownloadOffer({
  row,
  license,
  delivery,
  version,
}: {
  row: JobRow
  license: LicenseStatus
  delivery: Delivery | undefined
  version: string | undefined
}) {
  const queryClient = useQueryClient()
  const downloading = delivery?.phase === "downloading"
  return (
    <>
      <Sentence>
        {intl.formatMessage({
          id: "jobs_row_not_downloaded_body",
          defaultMessage:
            "Your license includes this job. Download it to run it on this computer.",
        })}
      </Sentence>
      <Actions>
        <Button
          type="button"
          size="sm"
          disabled={downloading}
          aria-label={intl.formatMessage(
            { id: "jobs_row_download_aria", defaultMessage: "Download {job}" },
            { job: row.name }
          )}
          onClick={() => void downloadJobPacks(queryClient, license.jobs)}
        >
          {downloading ? (
            <Spinner data-icon="inline-start" />
          ) : (
            <Download01Icon data-icon="inline-start" />
          )}
          {intl.formatMessage({
            id: "jobs_row_download_button",
            defaultMessage: "Download",
          })}
        </Button>
        <ImportPackButton size="sm" disabled={downloading} />
      </Actions>
      <p className="text-sm text-pretty text-muted-foreground">
        {intl.formatMessage({
          id: "jobs_row_offline_body",
          defaultMessage:
            "No internet on this computer? Ask SurfSense support for the job pack file, then import it.",
        })}
      </p>
      <ExternalLink href={supportUrl("jobs_support", version)}>
        {intl.formatMessage({
          id: "jobs_row_support_link",
          defaultMessage: "Contact support",
        })}
      </ExternalLink>
    </>
  )
}

function Offer({
  row,
  license,
  delivery,
  onOpenLicense,
}: {
  row: JobRow
  license: LicenseStatus
  delivery: Delivery | undefined
  onOpenLicense: () => void
}) {
  const version = useAppDetails().data?.version
  switch (row.kind) {
    case "available":
      return null
    case "not_downloaded":
      return (
        <DownloadOffer
          row={row}
          license={license}
          delivery={delivery}
          version={version}
        />
      )
    case "locked_none":
      return (
        <>
          <Sentence>
            {intl.formatMessage({
              id: "jobs_row_locked_none_body",
              defaultMessage:
                "Comes with a SurfSense Business license. Try it free for 14 days.",
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
            {intl.formatMessage({
              id: "jobs_row_locked_trial_body",
              defaultMessage:
                "Your license doesn’t include this job. It comes with a Business license, which you can try free for 14 days.",
            })}
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
              id: "jobs_row_locked_paid_body",
              defaultMessage:
                "Your {plan} license doesn’t include this job: jobs come with Business. If your license has moved to Business, Check for renewal fetches its new file.",
            },
            { plan: planName(license) }
          )}
        />
      )
    case "trial_ended":
      return (
        <>
          <Sentence>
            {intl.formatMessage({
              id: "jobs_row_trial_ended_body",
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
          sentence={intl.formatMessage({
            id: "jobs_row_expired_body",
            defaultMessage:
              "Your license has ended, so this job can’t run. If it was renewed, Check for renewal fetches the new file.",
          })}
        />
      )
    case "clock":
      return (
        <Sentence>
          {intl.formatMessage({
            id: "jobs_row_clock_body",
            defaultMessage:
              "This computer’s clock is behind the last time SurfSense ran. Set the clock right to run this job.",
          })}
        </Sentence>
      )
    case "no_entitlement":
      return (
        <Sentence>
          {intl.formatMessage({
            id: "jobs_row_locked_no_entitlement_body",
            defaultMessage: "No SurfSense license unlocks this job.",
          })}
        </Sentence>
      )
  }
}

/** One job, and the one step that would let it run here. */
export function JobRowItem({
  row,
  license,
  delivery,
  onRun,
  onSettings,
  onOpenLicense,
}: {
  row: JobRow
  license: LicenseStatus
  delivery: Delivery | undefined
  onRun: () => void
  onSettings: () => void
  onOpenLicense: () => void
}) {
  const available = row.kind === "available"
  return (
    <li className="flex flex-col gap-3 rounded-lg border p-4">
      <div className="flex items-start justify-between gap-6">
        <div className="flex min-w-0 flex-col gap-1">
          <h3 className="text-sm font-medium text-balance">{row.name}</h3>
          {row.description ? (
            <p className="text-sm text-pretty text-muted-foreground">
              {row.description}
            </p>
          ) : null}
          {available && row.version ? (
            <p className="text-xs text-muted-foreground tabular-nums">
              {intl.formatMessage(
                {
                  id: "jobs_row_version_label",
                  defaultMessage: "Version {version}",
                },
                { version: row.version }
              )}
            </p>
          ) : null}
        </div>
        {available ? (
          <div className="flex shrink-0 items-center gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              aria-label={intl.formatMessage(
                {
                  id: "jobs_row_settings_aria",
                  defaultMessage: "{job} settings",
                },
                { job: row.name }
              )}
              onClick={onSettings}
            >
              {intl.formatMessage({
                id: "jobs_row_settings_button",
                defaultMessage: "Settings",
              })}
            </Button>
            <Button
              type="button"
              size="sm"
              aria-label={intl.formatMessage(
                { id: "jobs_row_run_aria", defaultMessage: "Run {job}" },
                { job: row.name }
              )}
              onClick={onRun}
            >
              {intl.formatMessage({
                id: "jobs_row_run_button",
                defaultMessage: "Run",
              })}
            </Button>
          </div>
        ) : null}
      </div>
      <Offer
        row={row}
        license={license}
        delivery={delivery}
        onOpenLicense={onOpenLicense}
      />
      <DeliveryLine
        delivery={delivery}
        job={row.name}
        installedVersions={row.versions}
        place="row"
        showFailure={row.kind === "not_downloaded"}
      />
    </li>
  )
}
