import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useLicense } from "@/features/license/use-license"
import { intl } from "@/i18n/intl"

import { JobRowItem } from "./job-row"
import { jobRows } from "./job-rows"
import { LicenseOffer } from "./license-offer"
import { useDeliveries } from "./packs/download-job-packs"
import { JobRunsList } from "./runs/job-runs-list"
import { useJobPacks } from "./use-job-packs"

/** Every job SurfSense sells or this computer has, then the workspace's recent runs. */
export function JobList({
  workspaceId,
  onRun,
  onSettings,
  onOpenRun,
  onOpenLicense,
}: {
  workspaceId: number
  onRun: (job: string, title: string) => void
  onSettings: (job: string, title: string) => void
  onOpenRun: (runId: number) => void
  onOpenLicense: () => void
}) {
  const license = useLicense()
  const packs = useJobPacks()
  const deliveries = useDeliveries()

  if (license.isPending || packs.isPending)
    return (
      <div className="flex flex-col gap-3">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    )

  if (license.error || packs.error)
    return (
      <div className="flex flex-col items-start gap-2">
        <p role="alert" className="text-sm text-destructive">
          {intl.formatMessage({
            id: "jobs_list_error",
            defaultMessage: "Could not load your jobs.",
          })}
        </p>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => {
            if (license.error) void license.refetch()
            if (packs.error) void packs.refetch()
          }}
        >
          {intl.formatMessage({
            id: "jobs_list_retry_button",
            defaultMessage: "Try again",
          })}
        </Button>
      </div>
    )

  const rows = jobRows(packs.data, license.data)
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3">
        <LicenseOffer
          rows={rows}
          license={license.data}
          onOpenLicense={onOpenLicense}
        />
        <ul className="flex flex-col gap-3">
          {rows.map((row) => (
            <JobRowItem
              key={row.key}
              row={row}
              license={license.data}
              delivery={
                row.entitlement === null
                  ? undefined
                  : deliveries[row.entitlement]
              }
              onRun={() => row.job && onRun(row.job, row.name)}
              onSettings={() => row.job && onSettings(row.job, row.name)}
            />
          ))}
        </ul>
      </div>
      <JobRunsList
        workspaceId={workspaceId}
        packs={packs.data}
        offered={rows.some((row) => row.kind === "available")}
        onOpenRun={onOpenRun}
      />
    </div>
  )
}
