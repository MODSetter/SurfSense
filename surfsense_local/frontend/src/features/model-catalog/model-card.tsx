import { useId, useState } from "react"
import {
  ChevronDownIcon,
  DownloadIcon,
  SparklesIcon,
  Trash2Icon,
} from "@/components/ui/icons"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { cn } from "@/lib/utils"
import type { LocalBuild, LocalRow } from "./api"
import { FitBadge, FitReason } from "./fit-badge"
import { InstallProgress } from "./install-progress"
import { installView } from "./install-view"
import type { InstallState } from "./use-model-catalog"

const formatSize = (bytes: number) =>
  `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(bytes / 1e9)} GB`

function BuildAction({
  build,
  label,
  installState,
  disabled,
  runtimeAvailable,
  onAction,
}: {
  build: LocalBuild
  label: string
  installState: InstallState
  disabled: boolean
  runtimeAvailable: boolean
  onAction: (build: LocalBuild) => void
}) {
  const isInstalling =
    installState.status === "installing" &&
    installState.catalogId === build.catalog_id
  const installed = build.installed_as !== null
  // Only physics refuses. Reduced speed installs exactly like full speed.
  const cannotInstall = !installed && (!build.can_install || !runtimeAvailable)

  if (build.selected) {
    return (
      <Button type="button" size="sm" variant="outline" disabled>
        In use
      </Button>
    )
  }
  return (
    <Button
      type="button"
      size="sm"
      className="whitespace-nowrap"
      disabled={disabled || cannotInstall}
      aria-label={`${installed ? "Use" : "Download"} ${label} ${build.quantization}`}
      onClick={() => onAction(build)}
    >
      {/* A disabled button still reading "Download" while its own bar fills
          reads as unavailable rather than busy, so it names the phase. */}
      {isInstalling ? (
        <>
          <span className="animate-spin" data-icon="inline-start">
            <Spinner className="size-3.5" />
          </span>
          {installView(installState.event).short}
        </>
      ) : (
        <>
          {!installed ? <DownloadIcon data-icon="inline-start" /> : null}
          {installed ? "Use" : "Download"}
        </>
      )}
    </Button>
  )
}

export function ModelCard({
  row,
  installState,
  actionsDisabled,
  runtimeAvailable,
  onAction,
  onCancel,
  onDelete,
}: {
  row: LocalRow
  installState: InstallState
  actionsDisabled: boolean
  runtimeAvailable: boolean
  onAction: (build: LocalBuild) => void
  onCancel: () => void
  onDelete?: (build: LocalBuild) => void
}) {
  const buildsId = useId()
  const [open, setOpen] = useState(false)
  // The server chose it; the card only finds it among the builds it lists.
  const lead = row.builds.find((b) => b.quantization === row.lead?.quantization)
  if (!lead) return null

  const installingHere =
    installState.status === "installing" &&
    row.builds.some((b) => b.catalog_id === installState.catalogId)
  const others = row.builds.filter((b) => b !== lead)

  return (
    <article className="px-3 py-2 transition-colors hover:bg-muted/20">
      <div className="flex min-h-9 items-center justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-0.5">
          <div className="flex min-w-0 items-center gap-2">
            {row.recommended ? (
              <SparklesIcon
                aria-label="Recommended for this computer"
                className="size-3.5 shrink-0 text-notice"
              />
            ) : null}
            <p className="truncate text-sm font-medium">{row.name}</p>
            <FitBadge fit={lead.fit} copy={lead.badge} />
            {row.support.reads_images ? (
              <Badge variant="outline">Reads images</Badge>
            ) : null}
            <span className="shrink-0 text-xs text-muted-foreground">
              {lead.quantization} · {formatSize(lead.footprint_bytes)}
            </span>
          </div>
          {row.runnable ? (
            <FitReason copy={lead.badge} />
          ) : (
            <p className="text-xs text-muted-foreground">
              {row.not_runnable_reason}
            </p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {row.runnable ? (
            <BuildAction
              build={lead}
              label={row.name}
              installState={installState}
              disabled={actionsDisabled}
              runtimeAvailable={runtimeAvailable}
              onAction={onAction}
            />
          ) : null}
          {lead.installed_as && onDelete ? (
            <Button
              type="button"
              size="icon-sm"
              variant="destructive"
              disabled={actionsDisabled}
              aria-label={`Delete ${row.name}`}
              onClick={() => onDelete(lead)}
            >
              <Trash2Icon />
            </Button>
          ) : null}
        </div>
      </div>

      {others.length > 0 && row.runnable ? (
        <div className="mt-1">
          <button
            type="button"
            aria-expanded={open}
            aria-controls={buildsId}
            className="flex items-center gap-1 rounded-sm text-xs text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            onClick={() => setOpen((value) => !value)}
          >
            <ChevronDownIcon
              aria-hidden="true"
              className={cn(
                "size-3 transition-transform motion-reduce:transition-none",
                open && "rotate-180"
              )}
            />
            {open ? "Hide other builds" : `${others.length} other builds`}
          </button>
          {open ? (
            <ul
              id={buildsId}
              className="mt-1 flex flex-col divide-y rounded-lg border"
              aria-label={`Builds of ${row.name}`}
            >
              {others.map((build) => (
                <li
                  key={build.catalog_id || build.quantization}
                  className="flex items-center justify-between gap-3 px-2.5 py-1.5"
                >
                  <div className="flex min-w-0 items-center gap-2">
                    <span className="font-mono text-xs">
                      {build.quantization}
                    </span>
                    <FitBadge fit={build.fit} copy={build.badge} />
                    <span className="text-xs text-muted-foreground tabular-nums">
                      {formatSize(build.footprint_bytes)}
                    </span>
                  </div>
                  <BuildAction
                    build={build}
                    label={row.name}
                    installState={installState}
                    disabled={actionsDisabled}
                    runtimeAvailable={runtimeAvailable}
                    onAction={onAction}
                  />
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      {installingHere || !runtimeAvailable ? (
        <div className="mt-2 flex flex-col gap-2">
          {installingHere && installState.status === "installing" ? (
            <InstallProgress event={installState.event} onCancel={onCancel} />
          ) : null}
          {!runtimeAvailable ? (
            <p className="text-xs text-destructive">
              The local runtime is unavailable.
            </p>
          ) : null}
        </div>
      ) : null}
    </article>
  )
}
