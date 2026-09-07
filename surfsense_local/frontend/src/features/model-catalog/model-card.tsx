import { CheckIcon, DownloadIcon } from "@/components/ui/icons"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import type { CatalogRow } from "./api"
import { InstallProgress } from "./install-progress"
import type { InstallState } from "./use-model-catalog"

const fitLabels = {
  perfect: "Perfect fit",
  good: "Good fit",
  marginal: "Marginal",
  too_tight: "Too tight",
  unknown: "Unknown fit",
} as const

const value = (amount: number | null, format: (known: number) => string) =>
  amount === null ? "Unknown" : format(amount)

const decimal = (amount: number) =>
  new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(amount)

const compact = (amount: number) =>
  new Intl.NumberFormat(undefined, {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(amount)

function parameters(row: CatalogRow) {
  if (row.parameter_count === null) {
    return "Unknown"
  }
  if (typeof row.parameter_count === "string") {
    return row.parameter_count
  }
  return compact(row.parameter_count)
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
    <Card className="gap-4 py-4 [--card-spacing:--spacing(4)]">
      <CardHeader className="gap-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <CardTitle className="truncate text-base">{row.label}</CardTitle>
            <p className="text-xs text-muted-foreground">
              {row.family} · {row.publisher || "Unknown publisher"}
            </p>
          </div>
          <div className="flex flex-wrap gap-1.5">
            <Badge
              variant={
                row.fit === "too_tight"
                  ? "destructive"
                  : row.fit === "perfect"
                    ? "default"
                    : "secondary"
              }
            >
              {fitLabels[row.fit]}
            </Badge>
            {row.selected ? (
              <Badge variant="outline">
                <CheckIcon data-icon="inline-start" />
                Selected
              </Badge>
            ) : row.installed ? (
              <Badge variant="outline">Installed</Badge>
            ) : null}
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs sm:grid-cols-4">
          <div>
            <dt className="text-muted-foreground">Parameters</dt>
            <dd>{parameters(row)}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Quantization</dt>
            <dd>{row.quantization || "Unknown"}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Memory</dt>
            <dd>
              {value(
                row.memory_required_gb,
                (amount) => `${decimal(amount)} GB`
              )}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Download</dt>
            <dd>
              {value(row.disk_size_gb, (amount) => `${decimal(amount)} GB`)}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Speed</dt>
            <dd>
              {value(row.estimated_tps, (amount) => `${decimal(amount)} tok/s`)}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Usable context</dt>
            <dd>
              {value(row.effective_context_length, (amount) => compact(amount))}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Runtime</dt>
            <dd>{row.runtime || "Unknown"}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">License</dt>
            <dd>{row.license || "Unknown"}</dd>
          </div>
        </dl>
        <details className="text-xs text-muted-foreground">
          <summary className="cursor-pointer">Estimate details</summary>
          <p className="mt-1">
            Confidence: {row.estimate_confidence || "Unknown"}. Prefill:{" "}
            {value(row.prefill_tps, (amount) => `${decimal(amount)} tok/s`)}.
            Time to first token:{" "}
            {value(row.ttft_ms, (amount) => `${decimal(amount)} ms`)}.
          </p>
        </details>
        {row.warnings.map((warning) => (
          <p
            key={warning}
            className="text-xs text-amber-700 dark:text-amber-400"
          >
            {warning}
          </p>
        ))}
        {!runtimeAvailable ? (
          <p className="text-xs text-destructive">
            The {row.runtime} runtime is unavailable.
          </p>
        ) : null}
        {isInstalling ? (
          <InstallProgress event={installState.event} onCancel={onCancel} />
        ) : null}
        {rowResult?.status === "error" ? (
          <p className="text-xs text-destructive">{rowResult.message}</p>
        ) : null}
        {rowResult?.status === "cancelled" ? (
          <p className="text-xs text-muted-foreground">
            Installation cancelled. You can retry.
          </p>
        ) : null}
      </CardContent>
      <CardFooter className="justify-end">
        {row.selected ? (
          <Button type="button" size="sm" variant="outline" disabled>
            In use
          </Button>
        ) : (
          <Button
            type="button"
            size="sm"
            disabled={actionsDisabled || cannotInstall}
            onClick={() => onAction(row)}
          >
            {!row.installed ? <DownloadIcon data-icon="inline-start" /> : null}
            {row.installed ? "Use" : "Download & Use"}
          </Button>
        )}
      </CardFooter>
    </Card>
  )
}
