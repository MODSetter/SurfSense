import { Badge } from "@/components/ui/badge"
import { DotIcon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

import type { LocalBuild, LocalRow } from "../chat/api"
import { BuildAction } from "../chat/build-action"
import { FitBadge } from "../chat/fit-badge"
import { InstallProgress } from "../chat/install-progress"
import type { InstallJob } from "../installs/api"
import { jobFor } from "../installs/job-state"
import { appName } from "./app-name"

const formatSize = (bytes: number) =>
  intl.formatNumber(bytes / 1e9, {
    style: "unit",
    unit: "gigabyte",
    maximumFractionDigits: 1,
  })

/** The facts a found model's header states, one line. */
function Details({ row, build }: { row: LocalRow; build: LocalBuild }) {
  const found = row.found_in
  const parts = [
    build.quantization,
    formatSize(build.footprint_bytes),
    found?.parameters
      ? intl.formatMessage(
          {
            id: "models_elsewhere_parameters_label",
            defaultMessage: "{count, number, ::compact-short} parameters",
          },
          { count: found.parameters }
        )
      : null,
    row.support.context
      ? intl.formatMessage(
          {
            id: "models_elsewhere_context_label",
            defaultMessage: "{tokens, number, ::compact-short} context",
          },
          { tokens: row.support.context }
        )
      : null,
  ].filter((part): part is string => part !== null)
  return (
    <p className="flex flex-wrap items-center gap-x-1 text-xs text-muted-foreground">
      {parts.map((part, index) => (
        <span key={part} className="flex items-center gap-1 tabular-nums">
          {index > 0 ? <DotIcon aria-hidden="true" className="size-3" /> : null}
          {part}
        </span>
      ))}
    </p>
  )
}

/**
 * One chat model another app downloaded: whose folder it is in, what its header
 * says, how it fits here, and Use, which loads it where it lies.
 */
export function FoundModelRow({
  row,
  installs,
  disabled,
  onInstall,
  onUse,
  onCancel,
}: {
  row: LocalRow
  installs: readonly InstallJob[]
  disabled: boolean
  /** Record it and load it in place: the build's install, nothing downloaded. */
  onInstall: (build: LocalBuild) => void
  /** Already used in place: choose it by its runtime name. */
  onUse: (name: string) => void
  onCancel: (jobId: string) => void
}) {
  const build = row.builds[0]
  if (!build) return null
  const job = jobFor(installs, build.catalog_id)
  const source = row.found_in?.source
  return (
    <li className="flex flex-col gap-2 px-4 py-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-0.5">
          <div className="flex min-w-0 items-center gap-2">
            <span className="truncate text-sm font-medium">{row.name}</span>
            {row.found_in ? (
              <Badge variant="outline" className="shrink-0">
                {appName(row.found_in.app)}
              </Badge>
            ) : null}
            {row.support.reads_images ? (
              <Badge variant="secondary" className="shrink-0">
                {intl.formatMessage({
                  id: "models_elsewhere_vision_label",
                  defaultMessage: "Vision",
                })}
              </Badge>
            ) : null}
            <FitBadge fit={build.fit} copy={build.badge} />
          </div>
          <Details row={row} build={build} />
          {/* Which file it is, for a person with two of the same model. */}
          {source && source !== row.name ? (
            <p
              className="truncate text-xs text-muted-foreground"
              title={row.found_in?.path}
            >
              {source}
            </p>
          ) : null}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <BuildAction
            build={build}
            label={row.name}
            installs={installs}
            disabled={disabled}
            inPlace
            onAction={() =>
              build.installed_as ? onUse(build.installed_as) : onInstall(build)
            }
          />
        </div>
      </div>
      {job ? (
        <InstallProgress event={job.event} onCancel={() => onCancel(job.id)} />
      ) : null}
    </li>
  )
}
