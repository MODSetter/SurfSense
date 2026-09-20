import { Fragment, useId, useState, type ReactNode } from "react"
import { CircleAlertIcon, DotIcon, Trash2Icon } from "@/components/ui/icons"

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
import { Spinner } from "@/components/ui/spinner"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"
import type { Budget, CatalogRow, RepoBuild } from "./api"
import { LocalImageModel } from "./local-image-model"
import { ModelCard } from "./model-card"
import { ModelFamilyGroup } from "./model-family-group"
import { ModelSearch } from "./model-search"
import { useModelCatalog } from "./use-model-catalog"
import type { ModelSelection } from "@/features/model-selection/api"

function messageFrom(error: unknown) {
  return error instanceof Error ? error.message : "An unexpected error occurred"
}

/**
 * What this machine has, in one line. No scan and no button: the figure comes
 * from the runtime's own allocator in about 180ms, so there is nothing to wait
 * for and nothing to trigger.
 */
function hardwareSummary(budget: Budget | undefined) {
  const gb = (bytes: number) =>
    `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(bytes / 1e9)} GB`
  if (!budget) {
    return ["Checking this computer"]
  }
  if (!budget.has_gpu) {
    return [
      "Runs on your processor",
      `${gb(budget.ram_available_bytes)} memory`,
    ]
  }
  return [
    budget.uma ? "Apple Silicon GPU" : "Graphics card",
    `${gb(budget.device_total_bytes)} memory`,
  ]
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
  headerAction,
  children,
  emptyMessage,
  listMinHeight,
}: {
  title: string
  description: string
  rows: CatalogRow[]
  headerAction?: ReactNode
  children: (row: CatalogRow) => ReactNode
  // Shown instead of the row list when `rows` is empty but the section
  // should still render (e.g. a search with no matches) — omit this prop to
  // keep the earlier behavior of hiding the section entirely when empty.
  emptyMessage?: string
  // Reserves this much height regardless of how few rows are showing, so a
  // filter that removes rows leaves blank space below instead of shrinking
  // the page's scrollable area (which is what causes a scroll-position jump).
  listMinHeight?: number
}) {
  const headingId = useId()
  if (rows.length === 0 && emptyMessage === undefined) {
    return null
  }
  return (
    <section className="flex flex-col gap-2.5" aria-labelledby={headingId}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id={headingId} className="font-heading text-sm font-medium">
            {title}
          </h2>
          <p className="text-xs text-muted-foreground">{description}</p>
        </div>
        {headerAction}
      </div>
      <div
        data-slot="catalog-section-list"
        className="flex flex-col gap-2.5"
        style={listMinHeight ? { minHeight: listMinHeight } : undefined}
      >
        {rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">{emptyMessage}</p>
        ) : null}
        {[...grouped(rows)].map(([family, familyRows]) => (
          <ModelFamilyGroup key={family} family={family}>
            {familyRows.map((row) => (
              // model_id, not catalog_id: the latter is an opaque install
              // token that the server may reissue, and using it as a key would
              // remount the row each time. model_id is stable, so it updates
              // in place instead.
              <li key={row.model_id}>{children(row)}</li>
            ))}
          </ModelFamilyGroup>
        ))}
      </div>
    </section>
  )
}

export function ModelCatalogPage({
  allowDelete = false,
  scrollable = true,
  disabled = false,
  onModelUnavailable,
  onModelsChanged,
  onSelected,
}: {
  allowDelete?: boolean
  // False when an ancestor already scrolls this page as part of a bigger
  // region — see ModelSelectionContent.
  scrollable?: boolean
  disabled?: boolean
  onModelUnavailable?: () => void
  onModelsChanged?: () => void
  onSelected?: (selection: ModelSelection) => void
}) {
  const {
    catalog,
    install,
    installState,
    cancelInstall,
    deleteModel,
    selectInstalled,
  } = useModelCatalog(onSelected, onModelUnavailable, onModelsChanged)
  // Either list can offer deletion, and both need the same confirmation, so
  // this holds the minimum both rows share rather than a whole catalog row.
  const [pendingDelete, setPendingDelete] = useState<{
    label: string
    variant_model_id: string
    selected: boolean
  } | null>(null)

  // No skeleton: the catalog is the manifest plus a directory listing, priced
  // locally, so it resolves as fast as any other page fetch and a loading state
  // would only ever flash.
  if (catalog.isPending) {
    return null
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
  const curatedSection = {
    title: "Tested by SurfSense",
    description: "Models we have run, priced against this computer.",
    rows: data.curated ?? [],
  }
  const busy =
    disabled ||
    install.isPending ||
    selectInstalled.isPending ||
    deleteModel.isPending

  // A searched build and a curated row install through the same call, because
  // the id is opaque either way and the server cannot tell them apart.
  const installBuild = (build: RepoBuild) => {
    if (!busy) {
      install.mutate(build)
    }
  }

  const act = (row: CatalogRow) => {
    if (busy) {
      return
    }
    // No confirmation for a partial fit. It runs, slower, and llama.cpp places
    // the layers; only physics blocks, and that is already `can_install`.
    if (row.installed) {
      selectInstalled.mutate(row)
    } else {
      install.mutate(row)
    }
  }

  const onDeleteRow = (row: CatalogRow) =>
    setPendingDelete({
      label: row.label,
      variant_model_id: row.variant_model_id,
      selected: row.selected,
    })

  const card = (row: CatalogRow) => (
    <ModelCard
      row={row}
      installState={installState}
      actionsDisabled={busy}
      runtimeAvailable
      onAction={act}
      onCancel={cancelInstall}
      onDelete={allowDelete ? onDeleteRow : undefined}
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
    <div className={cn("flex flex-col gap-5", scrollable && "h-full min-h-0")}>
      <div className="rounded-lg bg-muted/50 p-3">
        <p className="flex items-center text-sm font-medium">
          {hardwareSummary(data.budget).map((part, index) => (
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
          Every model below is priced against this computer.
        </p>
      </div>

      <ScrollShadow className="flex-1" scroll={scrollable}>
        <div className="flex flex-col gap-5 pb-3">
          {(data.installed ?? []).length > 0 ? (
            <section className="flex flex-col gap-2.5">
              <div>
                <h2 className="font-heading text-sm font-medium">Installed</h2>
                <p className="text-xs text-muted-foreground">
                  Already on this machine.
                </p>
              </div>
              <ul className="divide-y overflow-hidden rounded-xl border bg-card">
                {(data.installed ?? []).map((row) => (
                  <li
                    key={row.model_id}
                    className="flex items-center justify-between gap-3 px-3 py-2"
                  >
                    <span className="truncate text-sm font-medium">
                      {row.model_id}
                    </span>
                    <div className="flex shrink-0 items-center gap-1">
                      {row.selected ? (
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled
                        >
                          In use
                        </Button>
                      ) : null}
                      {allowDelete ? (
                        <Button
                          type="button"
                          size="icon-sm"
                          variant="destructive"
                          disabled={busy}
                          aria-label={`Delete ${row.model_id}`}
                          onClick={() =>
                            setPendingDelete({
                              label: row.model_id,
                              variant_model_id: row.model_id,
                              selected: row.selected,
                            })
                          }
                        >
                          <Trash2Icon />
                        </Button>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          <LocalImageModel disabled={busy} />

          {(data.curated ?? []).length > 0 ? (
            <CatalogSection {...curatedSection}>{card}</CatalogSection>
          ) : null}

          <Separator className="my-4" />

          <ModelSearch onInstall={installBuild} disabled={busy} />

          {(data.curated ?? []).length + (data.installed ?? []).length === 0 ? (
            <Alert>
              <CircleAlertIcon />
              <AlertTitle>No local models are available</AlertTitle>
              <AlertDescription>
                Nothing is installed and no tested model could be read. You can
                search for one above, add a .gguf file from disk, or use an
                OpenAI compatible connection.
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
                : "This permanently removes the local model and its downloaded data from this machine."}
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
