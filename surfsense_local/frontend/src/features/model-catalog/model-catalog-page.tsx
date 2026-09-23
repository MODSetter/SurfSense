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
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ScrollShadow } from "@/components/ui/scroll-shadow"
import { Spinner } from "@/components/ui/spinner"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"
import type { Budget, GpuStatus, LocalBuild, LocalRow } from "./api"
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
 *
 * The status is read before the budget, because a machine whose graphics card
 * the runtime cannot reach is priced against its processor and would otherwise
 * be described as a machine that has no card at all. That is a sentence about
 * the user's hardware, and it would be wrong.
 */
function hardwareSummary(budget: Budget | undefined, gpuStatus?: GpuStatus) {
  const gb = (bytes: number) =>
    `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(bytes / 1e9)} GB`
  if (!budget) {
    return ["Checking this computer"]
  }
  if (gpuStatus === "broken_install") {
    return [
      "Graphics card not detected by the runtime. Reinstall to fix",
      `${gb(budget.ram_available_bytes)} memory`,
    ]
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

function grouped(rows: LocalRow[]) {
  const result = new Map<string, LocalRow[]>()
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
  children,
}: {
  title: string
  description: string
  rows: LocalRow[]
  children: (row: LocalRow) => ReactNode
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
      <div className="flex flex-col gap-2.5">
        {[...grouped(rows)].map(([family, familyRows]) => (
          <ModelFamilyGroup key={family} family={family}>
            {familyRows.map((row) => (
              // The row's id, not an install token: a token may be reissued,
              // and keying on it would remount the row each time.
              <li key={row.id}>{children(row)}</li>
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
    installed_as: string
    selected: boolean
    engine: LocalRow["engine"]
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
  const rows = data.rows ?? []
  const curated = rows.filter((row) => row.origin === "curated")
  // Everything on disk, curated or not: for a model installed from search this
  // list is the only place it appears.
  const installed = rows.flatMap((row) =>
    row.builds
      .filter((build) => build.installed_as !== null)
      .map((build) => ({
        row,
        build,
        installedAs: build.installed_as as string,
        label:
          row.origin === "curated"
            ? `${row.name} ${build.quantization}`
            : row.name,
      }))
  )
  const curatedSection = {
    title: "Tested by SurfSense",
    description: "Models we have run, priced against this computer.",
    rows: curated,
  }
  const busy =
    disabled ||
    install.isPending ||
    selectInstalled.isPending ||
    deleteModel.isPending

  // A searched build and a curated one install through the same call, because
  // the id is opaque either way and the server cannot tell them apart.
  const act = (build: LocalBuild, engine: LocalRow["engine"] = "llamacpp") => {
    if (busy) {
      return
    }
    // No confirmation for a partial fit. It runs, slower, and llama.cpp places
    // the layers; only physics blocks, and that is already `can_install`.
    if (build.installed_as) {
      selectInstalled.mutate({ installed_as: build.installed_as, engine })
    } else {
      install.mutate(build)
    }
  }

  const deleteBuild = (
    label: string,
    build: LocalBuild,
    engine: LocalRow["engine"]
  ) => {
    if (build.installed_as) {
      setPendingDelete({
        label,
        installed_as: build.installed_as,
        selected: build.selected,
        engine,
      })
    }
  }

  const card = (row: LocalRow) => (
    <ModelCard
      row={row}
      installState={installState}
      actionsDisabled={busy}
      runtimeAvailable
      onAction={(build) => act(build, row.engine)}
      onCancel={cancelInstall}
      onDelete={
        allowDelete
          ? (build) => deleteBuild(row.name, build, row.engine)
          : undefined
      }
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
          {hardwareSummary(data.budget, data.gpu_status).map((part, index) => (
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
          {installed.length > 0 ? (
            <section className="flex flex-col gap-2.5">
              <div>
                <h2 className="font-heading text-sm font-medium">Installed</h2>
                <p className="text-xs text-muted-foreground">
                  Already on this machine.
                </p>
              </div>
              <ul className="divide-y overflow-hidden rounded-xl border bg-card">
                {installed.map(({ row, build, installedAs, label }) => (
                  <li
                    key={installedAs}
                    className="flex items-center justify-between gap-3 px-3 py-2"
                  >
                    <div className="flex min-w-0 flex-col gap-0.5">
                      <div className="flex min-w-0 items-center gap-2">
                        <span className="truncate text-sm font-medium">
                          {label}
                        </span>
                        {build.reads_images ? (
                          <Badge variant="secondary">Vision</Badge>
                        ) : null}
                      </div>
                      {!row.runnable ? (
                        <p className="text-xs text-muted-foreground">
                          {row.not_runnable_reason}
                        </p>
                      ) : null}
                    </div>
                    <div className="flex shrink-0 items-center gap-1">
                      {build.selected ? (
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled
                        >
                          In use
                        </Button>
                      ) : row.runnable ? (
                        <Button
                          type="button"
                          size="sm"
                          disabled={busy}
                          aria-label={`Use ${label}`}
                          onClick={() =>
                            selectInstalled.mutate({
                              installed_as: installedAs,
                              engine: row.engine,
                            })
                          }
                        >
                          Use
                        </Button>
                      ) : null}
                      {allowDelete ? (
                        <Button
                          type="button"
                          size="icon-sm"
                          variant="destructive"
                          disabled={busy}
                          aria-label={`Delete ${label}`}
                          onClick={() => deleteBuild(label, build, row.engine)}
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

          {curated.length > 0 ? (
            <CatalogSection {...curatedSection}>{card}</CatalogSection>
          ) : null}

          <Separator className="my-4" />

          <ModelSearch
            onInstall={act}
            onCancel={cancelInstall}
            installState={installState}
            disabled={busy}
          />

          {curated.length + installed.length === 0 ? (
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
                ? pendingDelete.engine === "sdcpp"
                  ? "This is your current image model. Image formats need another one until you choose it."
                  : "This is your current model. Deleting it will require you to choose another model."
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
              {deleteModel.isPending ? "Deleting…" : "Delete model"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
