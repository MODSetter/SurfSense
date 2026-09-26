import { useId, useState } from "react"

import { CircleAlertIcon } from "@/components/ui/icons"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Separator } from "@/components/ui/separator"
import { intl } from "@/i18n/intl"

import type { ModelSelection } from "../../selection/api"
import { useSelect } from "../../selection/use-selection"
import { DeleteModelDialog } from "../../your-models/delete-model-dialog"
import type { YourModelRow } from "../../your-models/your-model-row"
import { useInstall } from "../installs/use-install"
import type { LocalBuild, LocalRow } from "./api"
import { HardwareSummary } from "./hardware-summary"
import { ModelCard } from "./model-card"
import { ModelFamilyGroup } from "./model-family-group"
import { ModelSearch } from "./model-search"
import { useDeleteLocalChatModel } from "./use-delete-local-chat-model"
import { useLocalChatCatalog } from "./use-local-chat-catalog"

function messageFrom(error: unknown) {
  return error instanceof Error
    ? error.message
    : intl.formatMessage({
        id: "models_download_chat_unexpected_error",
        defaultMessage: "An unexpected error occurred",
      })
}

/** The row `DeleteModelDialog` needs; it only reads `name` and `selected`. */
function deletableRow(build: LocalBuild, label: string): YourModelRow | null {
  if (!build.installed_as) return null
  return {
    key: build.installed_as,
    name: label,
    selected: build.selected,
    badges: [],
    note: null,
    target: null,
    removeId: build.installed_as,
  }
}

function byFamily(rows: LocalRow[]) {
  const result = new Map<string, LocalRow[]>()
  for (const row of rows) {
    // An empty family is kept empty; ModelFamilyGroup names it.
    result.set(row.family, [...(result.get(row.family) ?? []), row])
  }
  return result
}

/** Chat models to put on this computer: tested ones first, then all of Hugging Face. */
export function DownloadChatModels({
  onSelected,
  onModelUnavailable,
}: {
  onSelected?: (selection: ModelSelection) => void
  /** The model just deleted was the one in use; the page around this screen
   *  reports it, since it holds the app's model. */
  onModelUnavailable?: () => void
}) {
  const headingId = useId()
  const catalog = useLocalChatCatalog()
  // Downloading does not select: a model is chosen with Use once it is on disk.
  const { installs, install, cancel } = useInstall({ select: false })
  const select = useSelect("text_gen")
  const remove = useDeleteLocalChatModel(onModelUnavailable)
  const [deleting, setDeleting] = useState<{
    removeId: string
    row: YourModelRow
  } | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  // No skeleton: the catalog resolves as fast as any page fetch, so a loading
  // state would only ever flash.
  if (catalog.isPending) return null

  if (catalog.isError) {
    return (
      <Alert variant="destructive">
        <CircleAlertIcon />
        <AlertTitle>
          {intl.formatMessage({
            id: "models_download_chat_load_error",
            defaultMessage: "Could not load local models",
          })}
        </AlertTitle>
        <AlertDescription>{messageFrom(catalog.error)}</AlertDescription>
      </Alert>
    )
  }

  // The catalog also carries image and audio rows; only llama.cpp's are chat.
  const curated = catalog.data.rows.filter(
    (row) => row.origin === "curated" && row.engine === "llamacpp"
  )
  // A download does not block the rest: another one queues behind it.
  const busy = select.isPending || remove.isPending

  // No confirmation for a partial fit: it runs, slower, and llama.cpp places
  // the layers. Only physics blocks, and that is already `can_install`.
  const act = (build: LocalBuild) => {
    if (busy) return
    if (build.installed_as) {
      void select
        .mutateAsync({
          target: {
            provider: "llamacpp",
            connection_id: null,
            name: build.installed_as,
          },
        })
        .then((selection) => onSelected?.(selection))
        .catch(() => undefined)
    } else {
      void install(build.catalog_id)
    }
  }

  const confirmDelete = () => {
    if (!deleting) return
    setDeleteError(null)
    remove
      .mutateAsync(deleting.removeId)
      .then(() => setDeleteOpen(false))
      .catch((cause: unknown) => setDeleteError(messageFrom(cause)))
  }

  return (
    <div className="flex flex-col gap-5">
      <HardwareSummary
        budget={catalog.data.budget}
        gpuStatus={catalog.data.gpu_status}
      />

      {curated.length > 0 ? (
        <section className="flex flex-col gap-2.5" aria-labelledby={headingId}>
          <div>
            <h2 id={headingId} className="font-heading text-sm font-medium">
              {intl.formatMessage({
                id: "models_download_chat_curated_title",
                defaultMessage: "Tested by SurfSense",
              })}
            </h2>
            <p className="text-xs text-muted-foreground">
              {intl.formatMessage({
                id: "models_download_chat_curated_body",
                defaultMessage:
                  "Models we have run, priced against this computer.",
              })}
            </p>
          </div>
          {[...byFamily(curated)].map(([family, rows]) => (
            <ModelFamilyGroup key={family} family={family}>
              {rows.map((row) => (
                // The row's id, not an install token: a token may be reissued,
                // and keying on it would remount the row each time.
                <li key={row.id}>
                  <ModelCard
                    row={row}
                    installs={installs}
                    actionsDisabled={busy}
                    runtimeAvailable
                    onAction={act}
                    onCancel={cancel}
                    onDelete={(build) => {
                      const target = deletableRow(
                        build,
                        `${row.name} ${build.quantization}`
                      )
                      if (!target?.removeId) return
                      setDeleteError(null)
                      setDeleting({ removeId: target.removeId, row: target })
                      setDeleteOpen(true)
                    }}
                  />
                </li>
              ))}
            </ModelFamilyGroup>
          ))}
        </section>
      ) : (
        <Alert>
          <CircleAlertIcon />
          <AlertTitle>
            {intl.formatMessage({
              id: "models_download_chat_curated_empty",
              defaultMessage: "No tested models could be read",
            })}
          </AlertTitle>
          <AlertDescription>
            {intl.formatMessage({
              id: "models_download_chat_curated_empty_body",
              defaultMessage: "You can still search Hugging Face below.",
            })}
          </AlertDescription>
        </Alert>
      )}

      <Separator />

      <ModelSearch
        onInstall={act}
        onCancel={cancel}
        installs={installs}
        disabled={busy}
      />

      {select.isError ? (
        <p className="text-sm text-destructive">{messageFrom(select.error)}</p>
      ) : null}

      <DeleteModelDialog
        open={deleteOpen}
        row={deleting?.row ?? null}
        pending={remove.isPending}
        error={deleteError}
        onConfirm={confirmDelete}
        onOpenChange={setDeleteOpen}
        onOpenChangeComplete={(open) => {
          if (!open) setDeleting(null)
        }}
      />
    </div>
  )
}
