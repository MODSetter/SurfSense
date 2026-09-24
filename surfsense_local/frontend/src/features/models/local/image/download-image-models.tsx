import { useState } from "react"

import { CircleAlertIcon } from "@/components/ui/icons"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { intl } from "@/i18n/intl"

import { useSelect } from "../../selection/use-selection"
import { DeleteModelDialog } from "../../your-models/delete-model-dialog"
import type { YourModelRow } from "../../your-models/your-model-row"
import type { LocalBuild, LocalRow } from "../chat/api"
import { ModelCard } from "../chat/model-card"
import { ModelFamilyGroup } from "../chat/model-family-group"
import { useDeleteLocalImageModel } from "./use-delete-local-image-model"
import { useImageInstall } from "./use-image-install"
import { useLocalImageCatalog } from "./use-local-image-catalog"

function messageFrom(error: unknown) {
  return error instanceof Error
    ? error.message
    : intl.formatMessage({ id: "models_download_image_unexpected_error" })
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

/** Image models sd-server can run on this computer, listed as chat's are. */
export function DownloadImageModels() {
  const catalog = useLocalImageCatalog()
  const { installState, install, cancelInstall } = useImageInstall()
  const select = useSelect("image_gen")
  const remove = useDeleteLocalImageModel()
  const [deleting, setDeleting] = useState<{
    removeId: string
    row: YourModelRow
  } | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  if (catalog.isPending) return null

  if (catalog.isError) {
    return (
      <Alert variant="destructive">
        <CircleAlertIcon />
        <AlertTitle>
          {intl.formatMessage({ id: "models_download_image_load_error" })}
        </AlertTitle>
        <AlertDescription>{messageFrom(catalog.error)}</AlertDescription>
      </Alert>
    )
  }

  if (catalog.data.length === 0) {
    return (
      <Alert>
        <CircleAlertIcon />
        <AlertTitle>
          {intl.formatMessage({
            id: "models_download_image_unsupported_title",
          })}
        </AlertTitle>
        <AlertDescription>
          {intl.formatMessage({ id: "models_download_image_unsupported_body" })}
        </AlertDescription>
      </Alert>
    )
  }

  const busy =
    installState.status === "installing" || select.isPending || remove.isPending

  const act = (build: LocalBuild, label: string) => {
    if (busy) return
    if (build.installed_as) {
      void select
        .mutateAsync({
          target: {
            provider: "sdcpp",
            connection_id: null,
            name: build.installed_as,
          },
        })
        .catch(() => undefined)
    } else {
      void install(build.catalog_id, label)
    }
  }

  const confirmDelete = () => {
    if (!deleting) return
    setDeleteError(null)
    remove
      .mutateAsync(deleting.removeId)
      .then(() => setDeleting(null))
      .catch((cause: unknown) => setDeleteError(messageFrom(cause)))
  }

  return (
    <div className="flex flex-col gap-5">
      {[...byFamily(catalog.data)].map(([family, rows]) => (
        <ModelFamilyGroup key={family} family={family}>
          {rows.map((row) => (
            <li key={row.id}>
              <ModelCard
                row={row}
                installState={installState}
                actionsDisabled={busy}
                runtimeAvailable
                onAction={(build) =>
                  act(build, `${row.name} ${build.quantization}`)
                }
                onCancel={cancelInstall}
                onDelete={(build) => {
                  const target = deletableRow(
                    build,
                    `${row.name} ${build.quantization}`
                  )
                  if (!target?.removeId) return
                  setDeleteError(null)
                  setDeleting({ removeId: target.removeId, row: target })
                }}
              />
            </li>
          ))}
        </ModelFamilyGroup>
      ))}

      {select.isError ? (
        <p className="text-sm text-destructive">{messageFrom(select.error)}</p>
      ) : null}

      <DeleteModelDialog
        row={deleting?.row ?? null}
        pending={remove.isPending}
        error={deleteError}
        onConfirm={confirmDelete}
        onCancel={() => setDeleting(null)}
      />
    </div>
  )
}
