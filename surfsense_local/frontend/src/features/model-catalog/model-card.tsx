import { DownloadIcon } from "@/components/ui/icons"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import type { CatalogRow } from "./api"
import { InstallProgress } from "./install-progress"
import type { InstallState } from "./use-model-catalog"

const formatSize = (sizeGb: number) =>
  `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(sizeGb)} GB`

const fitLabel: Record<CatalogRow["fit"], string> = {
  perfect: "Great fit",
  good: "Good fit",
  marginal: "May be slow",
  too_tight: "Doesn't fit",
  unknown: "Fit unknown",
}

export function ModelCard({
  row,
  installState,
  actionsDisabled,
  runtimeAvailable,
  onAction,
  onCancel,
}: {
  row: CatalogRow
  installState: InstallState
  actionsDisabled: boolean
  runtimeAvailable: boolean
  onAction: (row: CatalogRow) => void
  onCancel: () => void
}) {
  const isInstalling =
    installState.status === "installing" &&
    installState.catalogId === row.catalog_id
  const rowResult =
    installState.status !== "idle" &&
    installState.status !== "installing" &&
    installState.catalogId === row.catalog_id
      ? installState
      : null
  const cannotInstall =
    !row.installed &&
    (!row.can_install || row.fit === "too_tight" || !runtimeAvailable)

  return (
    <article className="px-4 py-2.5 transition-colors hover:bg-muted/20">
      <div className="flex min-h-10 items-center justify-between gap-4">
        <div className="flex min-w-0 items-center gap-2">
          <p className="truncate text-sm font-medium">{row.label}</p>
          <Badge
            variant={
              row.fit === "too_tight"
                ? "destructive"
                : row.fit === "unknown"
                  ? "outline"
                  : "secondary"
            }
          >
            {fitLabel[row.fit]}
          </Badge>
          {row.disk_size_gb !== null ? (
            <span className="shrink-0 text-xs text-muted-foreground">
              {formatSize(row.disk_size_gb)}
            </span>
          ) : null}
        </div>
        <div className="shrink-0">
          {row.selected ? (
            <Button type="button" size="sm" variant="outline" disabled>
              In use
            </Button>
          ) : (
            <Button
              type="button"
              size="sm"
              className="whitespace-nowrap"
              disabled={actionsDisabled || cannotInstall}
              onClick={() => onAction(row)}
            >
              {!row.installed ? (
                <DownloadIcon data-icon="inline-start" />
              ) : null}
              {row.installed ? "Use" : "Download"}
            </Button>
          )}
        </div>
      </div>

      {isInstalling ||
      !runtimeAvailable ||
      rowResult?.status === "error" ||
      rowResult?.status === "cancelled" ? (
        <div className="mt-2 flex flex-col gap-2">
          {isInstalling ? (
            <InstallProgress event={installState.event} onCancel={onCancel} />
          ) : null}
          {!runtimeAvailable ? (
            <p className="text-xs text-destructive">
              The {row.runtime} runtime is unavailable.
            </p>
          ) : null}
          {rowResult?.status === "error" ? (
            <p className="text-xs text-destructive">{rowResult.message}</p>
          ) : null}
          {rowResult?.status === "cancelled" ? (
            <p className="text-xs text-muted-foreground">
              Installation cancelled. You can retry.
            </p>
          ) : null}
        </div>
      ) : null}
    </article>
  )
}
