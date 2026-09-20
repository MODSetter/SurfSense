import { DownloadIcon, SparklesIcon, Trash2Icon } from "@/components/ui/icons"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import type { CatalogRow } from "./api"
import { FitBadge, FitReason } from "./fit-badge"
import { InstallProgress } from "./install-progress"
import type { InstallState } from "./use-model-catalog"

const formatSize = (bytes: number) =>
  `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(bytes / 1e9)} GB`

export function ModelCard({
  row,
  installState,
  actionsDisabled,
  runtimeAvailable,
  onAction,
  onCancel,
  onDelete,
}: {
  row: CatalogRow
  installState: InstallState
  actionsDisabled: boolean
  runtimeAvailable: boolean
  onAction: (row: CatalogRow) => void
  onCancel: () => void
  onDelete?: (row: CatalogRow) => void
}) {
  const isInstalling =
    installState.status === "installing" &&
    installState.catalogId === row.catalog_id
  // Only physics refuses. Reduced speed installs exactly like full speed.
  const cannotInstall =
    !row.installed && (!row.can_install || !runtimeAvailable)

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
            <p className="truncate text-sm font-medium">{row.label}</p>
            <FitBadge fit={row.fit} copy={row.badge} />
            {row.capabilities.includes("vision") ? (
              <Badge variant="outline">Reads images</Badge>
            ) : null}
            <span className="shrink-0 text-xs text-muted-foreground">
              {formatSize(row.size_bytes)}
            </span>
          </div>
          <FitReason copy={row.badge} />
        </div>
        <div className="flex shrink-0 items-center gap-1">
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
          {row.installed && onDelete ? (
            <Button
              type="button"
              size="icon-sm"
              variant="destructive"
              disabled={actionsDisabled}
              aria-label={`Delete ${row.label}`}
              onClick={() => onDelete(row)}
            >
              <Trash2Icon />
            </Button>
          ) : null}
        </div>
      </div>

      {isInstalling || !runtimeAvailable ? (
        <div className="mt-2 flex flex-col gap-2">
          {isInstalling ? (
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
