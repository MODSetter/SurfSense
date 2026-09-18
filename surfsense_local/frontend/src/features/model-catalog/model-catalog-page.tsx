import { Fragment, useId, useState, type ReactNode } from "react"
import {
  CircleAlertIcon,
  DotIcon,
  RefreshCwIcon,
  SearchIcon,
} from "@/components/ui/icons"

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
import { Input } from "@/components/ui/input"
import { ScrollShadow } from "@/components/ui/scroll-shadow"
import { Spinner } from "@/components/ui/spinner"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"
import type {
  CatalogRow,
  HardwareProfile,
  ModelCatalog,
  RuntimeStatus,
} from "./api"
import { LocalImageModel } from "./local-image-model"
import { ModelCard } from "./model-card"
import { ModelFamilyGroup } from "./model-family-group"
import { useModelCatalog } from "./use-model-catalog"
import type { ModelSelection } from "@/features/model-selection/api"

// Reserved while "More models" is being searched, so narrowing to a handful
// of matches (or none) leaves blank space below them instead of shrinking
// the page's scrollable area — that shrink is what clamps scrollTop and
// yanks the whole page upward. Fixed rather than measured: it doesn't chase
// this catalog's actual row count, so there's no DOM measurement, no ref,
// and no effect that has to race the catalog finishing its own load.
const EXPLORE_SEARCH_RESERVED_HEIGHT = 540

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

function hardwareSummary(hardware: HardwareProfile | null, scanned: boolean) {
  if (!hardware) {
    // Never scanned (the common first-launch case, since nothing probes
    // hardware until the user asks) reads differently from a scan that was
    // attempted and failed — the latter also surfaces a warning banner.
    return [scanned ? "Hardware profile unavailable" : "Not detected yet"]
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
  headerAction,
  children,
  emptyMessage,
  listMinHeight,
}: {
  title: string
  description: string
  rows: CatalogRow[]
  catalog: ModelCatalog
  headerAction?: ReactNode
  children: (row: CatalogRow, available: boolean) => ReactNode
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
              // canonical_id, not catalog_id: the latter is an opaque,
              // refresh-sensitive install-plan token (it deliberately goes
              // stale on every rescan, so a stale install can't slip through)
              // — using it as a React key would remount every row on every
              // scan. canonical_id is stable across scan states for the same
              // model, so the row updates in place instead.
              <li key={row.canonical_id}>
                {children(
                  row,
                  runtimeAvailable(catalog.runtime_status[row.runtime])
                )}
              </li>
            ))}
          </ModelFamilyGroup>
        ))}
      </div>
    </section>
  )
}

function ScanHardwareCta({
  onScan,
  pending,
  search,
}: {
  onScan: () => void
  pending: boolean
  search: ReactNode
}) {
  return (
    <section className="flex flex-col gap-2.5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-heading text-sm font-medium">More models</h2>
          <p className="text-xs text-muted-foreground">
            Other compatible models, ranked for your machine.
          </p>
        </div>
        {search}
      </div>
      <div className="flex flex-col items-start gap-3 rounded-xl border border-dashed p-4">
        <p className="text-sm text-muted-foreground">
          Find every model that fits your machine, ranked best-first.
        </p>
        <Button
          type="button"
          size="sm"
          variant="default"
          disabled={pending}
          onClick={onScan}
        >
          {pending ? <Spinner data-icon="inline-start" /> : null}
          {pending ? "Scanning..." : "Scan hardware"}
        </Button>
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
    rescan,
    install,
    installState,
    cancelInstall,
    deleteModel,
    selectInstalled,
  } = useModelCatalog(onSelected, onModelUnavailable, onModelsChanged)
  const [exploreQuery, setExploreQuery] = useState("")
  const exploreQueryActive = exploreQuery.trim() !== ""
  const [pendingConfirmation, setPendingConfirmation] =
    useState<CatalogRow | null>(null)
  const [pendingDelete, setPendingDelete] = useState<CatalogRow | null>(null)

  // No skeleton: the catalog GET no longer probes hardware on an unrefreshed
  // load (see `LlmfitAdvisor.scan`), so it resolves as fast as any other
  // page fetch and a loading state would only ever flash.
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
  const seen = new Set<string>()
  const unique = (rows: CatalogRow[]) =>
    rows.filter((row) => {
      if (seen.has(row.catalog_id)) {
        return false
      }
      seen.add(row.catalog_id)
      return true
    })
  // Curated is always populated — the manifest's own 8 models, scan-free —
  // and never merges into "More models": scanning only ever adds a fit
  // badge to a row already here, never moves it elsewhere. "More models" is
  // fundamentally scan-derived, so it only exists once `data.scanned` is
  // true; until then a "Scan hardware" prompt takes its place.
  const curated = unique(data.curated)
  const explore = unique(data.explore)
  const installed = unique(data.installed)
  const curatedSection = {
    title: "Curated models",
    description: "Staff picks. Scan machine to see how well each one runs on your machine.",
    rows: curated,
  }
  const exploreQueryNormalized = exploreQuery.trim().toLowerCase()
  const filteredExplore =
    exploreQueryNormalized === ""
      ? explore
      : explore.filter((row) =>
          row.label.toLowerCase().includes(exploreQueryNormalized)
        )
  // Disabled (not hidden) until the first scan exists — there's nothing to
  // search yet, and a persistent, disabled control previews the feature
  // instead of the layout shifting once scanning finishes.
  const exploreSearchInput = (
    <div className="relative w-full max-w-[14rem] sm:w-auto">
      <SearchIcon className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
      <Input
        type="search"
        value={exploreQuery}
        placeholder="Search more models"
        aria-label="Search more models"
        disabled={!data.scanned}
        className="h-8 border-0 bg-secondary pl-8 text-sm focus-visible:border-0"
        onChange={(event) => setExploreQuery(event.target.value)}
      />
    </div>
  )
  const exploreSection = {
    title: "More models",
    description: "Other compatible models, best fit first.",
    rows: filteredExplore,
    emptyMessage: `No models match "${exploreQuery.trim()}".`,
    headerAction: exploreSearchInput,
  }
  const installedSection = {
    title: "Installed",
    description: "Local models already available on this machine.",
    rows: installed,
  }
  // Estimates reserve resources for SurfSense and may vary by workload.
  const busy =
    disabled ||
    install.isPending ||
    selectInstalled.isPending ||
    deleteModel.isPending

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
      scanned={data.scanned}
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
    <div className={cn("flex flex-col gap-5", scrollable && "h-full min-h-0")}>
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-muted/50 p-3">
        <div>
          <p className="flex items-center text-sm font-medium">
            {hardwareSummary(data.hardware, data.scanned).map((part, index) => (
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
            {data.scanned
              ? "Only models compatible with this machine are shown."
              : "Scan to filter by what fits your machine."}
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
          ) : data.scanned ? (
            <RefreshCwIcon data-icon="inline-start" />
          ) : null}
          {rescan.isPending
            ? "Scanning..."
            : data.scanned
              ? "Rescan hardware"
              : "Scan hardware"}
        </Button>
      </div>

      <ScrollShadow className="flex-1" scroll={scrollable}>
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

          {installedSection ? (
            <CatalogSection {...installedSection} catalog={data}>
              {card}
            </CatalogSection>
          ) : null}

          <LocalImageModel disabled={busy} />

          {curated.length > 0 ? (
            <CatalogSection {...curatedSection} catalog={data}>
              {card}
            </CatalogSection>
          ) : null}

          {curated.length > 0 && (explore.length > 0 || !data.scanned) ? (
            <Separator className="my-4" />
          ) : null}

          {data.scanned ? (
            explore.length > 0 ? (
              <CatalogSection
                {...exploreSection}
                catalog={data}
                listMinHeight={
                  exploreQueryActive
                    ? EXPLORE_SEARCH_RESERVED_HEIGHT
                    : undefined
                }
              >
                {card}
              </CatalogSection>
            ) : null
          ) : (
            <ScanHardwareCta
              onScan={() => rescan.mutate()}
              pending={rescan.isPending}
              search={exploreSearchInput}
            />
          )}

          {curated.length + explore.length + installed.length === 0 ? (
            <Alert>
              <CircleAlertIcon />
              <AlertTitle>No local models are available</AlertTitle>
              <AlertDescription>
                This machine has no compatible local configuration right now.
                You can still use an OpenAI-compatible connection.
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
