import type { ReactNode } from "react"
import { useQueryClient } from "@tanstack/react-query"

import { Button } from "@/components/ui/button"
import { Download01Icon } from "@/components/ui/icons"
import { Spinner } from "@/components/ui/spinner"
import { ExternalLink } from "@/features/about/external-link"
import { useAppDetails } from "@/features/about/use-app-details"
import type { LicenseStatus } from "@/features/license/api"
import { supportUrl } from "@/features/license/license-links"
import { intl } from "@/i18n/intl"

import type { JobRow } from "./job-rows"
import { isLicenseLock } from "./license-lock"
import { LicenseLockBadge } from "./license-lock-badge"
import { DeliveryLine } from "./packs/delivery-line"
import { downloadJobPacks, type Delivery } from "./packs/download-job-packs"
import { ImportPackButton } from "./packs/import-pack-button"

function Sentence({ children }: { children: ReactNode }) {
  return <p className="text-sm text-pretty">{children}</p>
}

function DownloadOffer({
  row,
  license,
  delivery,
}: {
  row: JobRow
  license: LicenseStatus
  delivery: Delivery | undefined
}) {
  const queryClient = useQueryClient()
  const version = useAppDetails().data?.version
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
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
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
      </div>
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

/** One job, and the one step of its own that would let it run here. What the
 *  license needs is offered once, above the list. */
export function JobRowItem({
  row,
  license,
  delivery,
  onRun,
  onSettings,
}: {
  row: JobRow
  license: LicenseStatus
  delivery: Delivery | undefined
  onRun: () => void
  onSettings: () => void
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
        {isLicenseLock(row.kind) ? <LicenseLockBadge lock={row.kind} /> : null}
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
      {row.kind === "not_downloaded" ? (
        <DownloadOffer row={row} license={license} delivery={delivery} />
      ) : null}
      {row.kind === "no_entitlement" ? (
        <Sentence>
          {intl.formatMessage({
            id: "jobs_row_locked_no_entitlement_body",
            defaultMessage: "No SurfSense license unlocks this job.",
          })}
        </Sentence>
      ) : null}
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
