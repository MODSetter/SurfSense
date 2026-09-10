import { Fragment, useId, useState, type ReactNode } from "react"
import { CircleAlertIcon, DotIcon, RefreshCwIcon } from "@/components/ui/icons"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { ScrollShadow } from "@/components/ui/scroll-shadow"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { Separator } from "@/components/ui/separator"
import type {
  CatalogRow,
  HardwareProfile,
  ModelCatalog,
  RuntimeStatus,
} from "./api"
import { ModelCard } from "./model-card"
import { ModelFamilyGroup } from "./model-family-group"
import { useModelCatalog } from "./use-model-catalog"
import type { ModelSelection } from "@/features/model-selection/api"

function messageFrom(error: unknown) {
  return error instanceof Error ? error.message : "An unexpected error occurred"
}

function runtimeAvailable(status: RuntimeStatus | undefined) {
  if (status === undefined) {
    return true
  }
  if (typeof status === "boolean") {
    return status
  }
  if (typeof status === "string") {
    return !["offline", "unavailable", "error", "stopped"].includes(
      status.toLowerCase()
    )
  }
  if (status.available !== undefined) {
    return status.available
  }
  if (status.healthy !== undefined) {
    return status.healthy
  }
  return !["offline", "unavailable", "error", "stopped"].includes(
    status.status?.toLowerCase() ?? ""
  )
}

function hardwareSummary(hardware: HardwareProfile | null) {
  if (!hardware) {
    return ["Hardware profile unavailable"]
  }
  const name = hardware.gpu_name ?? hardware.cpu_name
  const memory = hardware.total_ram_gb
  const parts = [name, memory !== null ? `${memory} GB memory` : null].filter(
    (part): part is string => part !== null
  )
  return parts.length > 0 ? parts : ["Hardware profile analyzed"]
}

function grouped(rows: CatalogRow[]) {
  const result = new Map<string, CatalogRow[]>()
  for (const row of rows) {
    const family = row.family || "Other"
    result.set(family, [...(result.get(family) ?? []), row])
  }
  return result
}

function CatalogSection({
  title,
  description,
  rows,
  catalog,
  children,
}: {
  title: string
  description: string
  rows: CatalogRow[]
  catalog: ModelCatalog
  children: (row: CatalogRow, available: boolean) => ReactNode
}) {
  const headingId = useId()
  if (rows.length === 0) {
    return null
  }
  return (
    <section className="flex flex-col gap-2.5" aria-labelledby={headingId}>
      <div>
        <h2 id={headingId} className="font-heading text-sm font-medium">
          {title}
        </h2>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      {[...grouped(rows)].map(([family, familyRows]) => (
        <ModelFamilyGroup key={family} family={family}>
          {familyRows.map((row) => (
            <li key={row.catalog_id}>
              {children(
                row,
                runtimeAvailable(catalog.runtime_status[row.runtime])
              )}
            </li>
          ))}
        </ModelFamilyGroup>
      ))}
    </section>
  )
}

export function ModelCatalogPage({
  allowDelete = false,
  disabled = false,
  onModelUnavailable,
  onModelsChanged,
  onSelected,
  installedFirst = false,
}: {
  allowDelete?: boolean
  disabled?: boolean
  onModelUnavailable?: () => void
  onModelsChanged?: () => void
  onSelected?: (selection: ModelSelection) => void
  installedFirst?: boolean
}) {
  const {
    catalog,
    rescan,
    install,
    installState,
    cancelInstall,
    deleteModel,
    selectInstalled,
  } = useModelCatalog(onSelected, onModelUnavailable, onModelsChanged)
  const [pendingConfirmation, setPendingConfirmation] =
    useState<CatalogRow | null>(null)
  const [pendingDelete, setPendingDelete] = useState<CatalogRow | null>(null)

  if (catalog.isPending) {
    return (
      <div
        className="flex h-full min-h-0 flex-col gap-5"
        role="status"
        aria-label="Scanning model catalog"
      >
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-muted/50 p-3">
          <div>
            <div className="flex items-center">
              <Skeleton
                data-slot="hardware-name-skeleton"
                className="h-5 w-14"
              />
              <DotIcon
                aria-hidden="true"
                className="size-3 shrink-0 text-muted-foreground"
              />
              <Skeleton
                data-slot="hardware-memory-skeleton"
                className="h-5 w-20"
              />
            </div>
            <p className="text-xs text-muted-foreground">
              Only models compatible with this computer are shown.
            </p>
          </div>
          <Button type="button" size="sm" variant="outline" disabled>
            <RefreshCwIcon data-icon="inline-start" />
            Rescan hardware
          </Button>
        </div>
        <ScrollShadow className="flex-1">
          <div className="flex flex-col gap-3">
            {[0, 1, 2].map((item) => (
              <Skeleton key={item} className="h-28 w-full rounded-xl" />
            ))}
          </div>
        </ScrollShadow>
      </div>
    )
  }

  if (catalog.isError || !catalog.data) {
    return (
      <Alert variant="destructive">
        <CircleAlertIcon />
        <AlertTitle>Could not load local models</AlertTitle>
        <AlertDescription>{messageFrom(catalog.error)}</AlertDescription>
      </Alert>
    )
  }

  const data = catalog.data
  const seen = new Set<string>()
  const unique = (rows: CatalogRow[]) =>
    rows.filter((row) => {
      if (seen.has(row.catalog_id)) {
        return false
      }
      seen.add(row.catalog_id)
      return true
    })
  const recommended = unique(data.recommended)
  const explore = unique(data.explore)
  const installed = unique(data.installed)
  const sections = (
    installedFirst
      ? [
          {
            title: "Installed",
            description: "Local models already available on this computer.",
            rows: installed,
          },
          {
            title: "Best for this computer",
            description: "SurfSense-tested models ranked for your hardware.",
            rows: recommended,
          },
          {
            title: "More models",
            description: "Other compatible models, best fit first.",
            rows: explore,
          },
        ]
      : [
          {
            title: "Best for this computer",
            description: "SurfSense-tested models ranked for your hardware.",
            rows: recommended,
          },
          {
            title: "More models",
            description: "Other compatible models, best fit first.",
            rows: explore,
          },
          {
            title: "Installed",
            description: "Local models already available on this computer.",
            rows: installed,
          },
        ]
  ).filter((section) => section.rows.length > 0)
  // Estimates reserve resources for SurfSense and may vary by workload.
  const busy =
    disabled ||
    install.isPending || selectInstalled.isPending || deleteModel.isPending

  const act = (row: CatalogRow) => {
    if (busy) {
      return
    }
    if (row.fit === "marginal") {
      setPendingConfirmation(row)
      return
    }
    if (row.installed) {
      selectInstalled.mutate(row)
    } else {
      install.mutate(row)
    }
  }

  const confirm = () => {
    const row = pendingConfirmation
    setPendingConfirmation(null)
    if (!row || busy) {
      return
    }
    if (row.installed) {
      selectInstalled.mutate(row)
    } else {
      install.mutate(row)
    }
  }

  const card = (row: CatalogRow, available: boolean) => (
    <ModelCard
      row={row}
      installState={installState}
      actionsDisabled={busy}
      runtimeAvailable={available}
      onAction={act}
      onCancel={cancelInstall}
      onDelete={allowDelete ? setPendingDelete : undefined}
    />
  )

  const confirmDelete = async () => {
    if (!pendingDelete || deleteModel.isPending) {
      return
    }
    try {
      await deleteModel.mutateAsync(pendingDelete)
      setPendingDelete(null)
    } catch {
      // The mutation error stays visible in the dialog.
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-muted/50 p-3">
        <div>
          <p className="flex items-center text-sm font-medium">
            {hardwareSummary(data.hardware).map((part, index) => (
              <Fragment key={part}>
                {index > 0 ? (
                  <DotIcon
                    aria-hidden="true"
                    className="size-3 shrink-0 text-muted-foreground"
                  />
                ) : null}
                <span>{part}</span>
              </Fragment>
            ))}
          </p>
          <p className="text-xs text-muted-foreground">
            Only models compatible with this computer are shown.
          </p>
        </div>
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={rescan.isPending || busy}
          onClick={() => rescan.mutate()}
        >
          {rescan.isPending ? (
            <Spinner data-icon="inline-start" />
          ) : (
            <RefreshCwIcon data-icon="inline-start" />
          )}
          {rescan.isPending ? "Rescanning..." : "Rescan hardware"}
        </Button>
      </div>

      <ScrollShadow className="flex-1">
        <div className="flex flex-col gap-5 pb-3">
          {data.warnings.map((warning) => (
            <Alert key={warning.code}>
              <CircleAlertIcon />
              <AlertTitle>Recommendations are degraded</AlertTitle>
              <AlertDescription>{warning.message}</AlertDescription>
            </Alert>
          ))}
          {rescan.isError ? (
            <p className="text-sm text-destructive">
              {messageFrom(rescan.error)}
            </p>
          ) : null}

          {sections.map((section, index) => (
            <Fragment key={section.title}>
              {index > 0 ? <Separator className="my-4" /> : null}
              <CatalogSection {...section} catalog={data}>
                {card}
              </CatalogSection>
            </Fragment>
          ))}

          {recommended.length + explore.length + installed.length === 0 ? (
            <Alert>
              <CircleAlertIcon />
              <AlertTitle>No local models are available</AlertTitle>
              <AlertDescription>
                This computer has no compatible local configuration right now.
                You can still use OpenRouter.
              </AlertDescription>
            </Alert>
          ) : null}
          {selectInstalled.isError ? (
            <p className="text-sm text-destructive">
              {messageFrom(selectInstalled.error)}
            </p>
          ) : null}
          {deleteModel.isError && pendingDelete === null ? (
            <p className="text-sm text-destructive">
              {messageFrom(deleteModel.error)}
            </p>
          ) : null}
        </div>
      </ScrollShadow>

      <AlertDialog
        open={pendingConfirmation !== null}
        onOpenChange={(open) => {
          if (!open) {
            setPendingConfirmation(null)
          }
        }}
      >
        <AlertDialogContent className="select-none">
          <AlertDialogHeader>
            <AlertDialogTitle>Use a marginal-fit model?</AlertDialogTitle>
            <AlertDialogDescription>
              This model may respond slowly or fail with long conversations. You
              can cancel and choose a better-fitting model.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirm}>
              Continue anyway
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog
        open={pendingDelete !== null}
        onOpenChange={(open) => {
          if (!open && !deleteModel.isPending) {
            setPendingDelete(null)
          }
        }}
      >
        <AlertDialogContent className="select-none">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {pendingDelete?.label}?</AlertDialogTitle>
            <AlertDialogDescription>
              {pendingDelete?.selected
                ? "This is your current model. Deleting it will require you to choose another model."
                : "This permanently removes the local model and its downloaded data from this computer."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          {deleteModel.isError ? (
            <p className="text-sm text-destructive">
              {messageFrom(deleteModel.error)}
            </p>
          ) : null}
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteModel.isPending}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={deleteModel.isPending}
              onClick={(event) => {
                event.preventDefault()
                void confirmDelete()
              }}
            >
              {deleteModel.isPending ? (
                <Spinner data-icon="inline-start" />
              ) : null}
              {deleteModel.isPending ? "Deleting..." : "Delete model"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
