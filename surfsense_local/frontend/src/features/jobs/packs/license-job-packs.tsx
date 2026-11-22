import { useQueryClient } from "@tanstack/react-query"

import { Button } from "@/components/ui/button"
import { Download01Icon } from "@/components/ui/icons"
import { Spinner } from "@/components/ui/spinner"
import { ExternalLink } from "@/features/about/external-link"
import { useAppDetails } from "@/features/about/use-app-details"
import { supportUrl } from "@/features/license/license-links"
import { intl } from "@/i18n/intl"

import { jobTitle } from "../catalog"
import { installedJobFor, installedVersionsFor } from "../job-rows"
import { useJobPacks } from "../use-job-packs"

import { DeliveryLine } from "./delivery-line"
import { downloadJobPacks, useDeliveries } from "./download-job-packs"
import { ImportPackButton } from "./import-pack-button"

/**
 * Settings › License's account of the license's jobs on this computer. Only an
 * active license downloads; one that ended, or whose clock is held, can still
 * import a pack file from support.
 */
export function LicenseJobPacks({
  jobs,
  canDownload,
  disabled,
}: {
  // The license's entitlement codes.
  jobs: readonly string[]
  canDownload: boolean
  // Another change to the license is under way.
  disabled: boolean
}) {
  const queryClient = useQueryClient()
  const packs = useJobPacks()
  const deliveries = useDeliveries()
  const version = useAppDetails().data?.version
  const codes = [...new Set(jobs)]
  const installedVersion = (code: string) =>
    installedJobFor(packs.data ?? [], code)?.version ?? null
  const downloading = codes.some(
    (code) => deliveries[code]?.phase === "downloading"
  )
  const missing = codes.some((code) => installedVersion(code) === null)

  return (
    <div className="mt-8 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-8">
        <div className="flex flex-col gap-1">
          <h3 className="text-sm font-medium text-balance">
            {intl.formatMessage({
              id: "jobs_license_title",
              defaultMessage: "Jobs on this computer",
            })}
          </h3>
          <p className="text-sm text-pretty text-muted-foreground">
            {intl.formatMessage({
              id: "jobs_license_body",
              defaultMessage:
                "SurfSense downloads the jobs your license includes from its license server, and checks for newer versions when it starts and once a day while you allow it. No internet on this computer? Ask SurfSense support for the job pack file, then import it.",
            })}
          </p>
        </div>
        <div className="flex shrink-0 items-start gap-2">
          <ImportPackButton disabled={disabled} className="items-end" />
          {canDownload ? (
            <Button
              type="button"
              variant="outline"
              disabled={disabled || downloading || packs.isPending}
              onClick={() => void downloadJobPacks(queryClient, codes)}
            >
              {downloading ? (
                <Spinner data-icon="inline-start" />
              ) : (
                <Download01Icon data-icon="inline-start" />
              )}
              {missing
                ? intl.formatMessage({
                    id: "jobs_license_download_button",
                    defaultMessage: "Download",
                  })
                : intl.formatMessage({
                    id: "jobs_license_update_button",
                    defaultMessage: "Check for updates",
                  })}
            </Button>
          ) : null}
        </div>
      </div>
      {packs.error ? (
        <p role="alert" className="text-sm text-destructive">
          {intl.formatMessage({
            id: "jobs_license_load_error",
            defaultMessage: "Could not read which jobs are on this computer.",
          })}
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {codes.map((code) => {
            const installed = installedVersion(code)
            const name = jobTitle(code)
            return (
              <li key={code} className="flex flex-col gap-0.5">
                <span className="text-sm">{name}</span>
                {packs.data ? (
                  <span className="text-sm text-muted-foreground tabular-nums">
                    {installed
                      ? intl.formatMessage(
                          {
                            id: "jobs_license_installed_label",
                            defaultMessage: "Version {version}",
                          },
                          { version: installed }
                        )
                      : intl.formatMessage({
                          id: "jobs_license_missing_label",
                          defaultMessage: "Not downloaded yet",
                        })}
                  </span>
                ) : null}
                <DeliveryLine
                  delivery={deliveries[code]}
                  job={name}
                  installedVersions={installedVersionsFor(
                    packs.data ?? [],
                    code
                  )}
                  place="license"
                  showFailure
                />
              </li>
            )
          })}
        </ul>
      )}
      <ExternalLink href={supportUrl("license_jobs_support", version)}>
        {intl.formatMessage({
          id: "jobs_license_support_link",
          defaultMessage: "Contact support",
        })}
      </ExternalLink>
    </div>
  )
}
