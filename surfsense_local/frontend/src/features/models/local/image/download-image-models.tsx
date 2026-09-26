import { useState } from "react"

import { CircleAlertIcon } from "@/components/ui/icons"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { intl } from "@/i18n/intl"

import { useSelect } from "../../selection/use-selection"
import { DeleteModelDialog } from "../../your-models/delete-model-dialog"
import type { YourModelRow } from "../../your-models/your-model-row"
import { useInstall } from "../installs/use-install"
import type { LocalBuild, LocalRow } from "../chat/api"
import { ModelCard } from "../chat/model-card"
import { ModelFamilyGroup } from "../chat/model-family-group"
import type { SdCppSlot } from "./api"
import { useDeleteLocalImageModel } from "./use-delete-local-image-model"
import { useLocalImageCatalog } from "./use-local-image-catalog"

const UNSUPPORTED_TITLE: Record<SdCppSlot, () => string> = {
  image_gen: () =>
    intl.formatMessage({
      id: "models_download_image_unsupported_title",
      defaultMessage: "Image models cannot run on this computer",
    }),
  image_edit: () =>
    intl.formatMessage({
      id: "models_download_image_edit_unsupported_title",
      defaultMessage: "Image editing models cannot run on this computer",
    }),
  video_gen: () =>
    intl.formatMessage({
      id: "models_download_video_unsupported_title",
      defaultMessage: "Video models cannot run on this computer",
    }),
}

function messageFrom(error: unknown) {
  return error instanceof Error
    ? error.message
    : intl.formatMessage({
        id: "models_download_image_unexpected_error",
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

/** Image models sd-server can run on this computer for `slot`, listed as
 *  chat's are. */
export function DownloadImageModels({
  slot = "image_gen",
}: {
  slot?: SdCppSlot
}) {
  const catalog = useLocalImageCatalog(slot)
  // Downloading does not select: a model is picked once it is on disk.
  const { installs, install, cancel } = useInstall({ select: false })
  const select = useSelect(slot)
  const remove = useDeleteLocalImageModel()
  const [deleting, setDeleting] = useState<{
    removeId: string
    row: YourModelRow
  } | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  if (catalog.isPending) return null

  if (catalog.isError) {
    return (
      <Alert variant="destructive">
        <CircleAlertIcon />
        <AlertTitle>
          {intl.formatMessage({
            id: "models_download_image_load_error",
            defaultMessage: "Could not load local image models",
          })}
        </AlertTitle>
        <AlertDescription>{messageFrom(catalog.error)}</AlertDescription>
      </Alert>
    )
  }

  if (catalog.data.length === 0) {
    return (
      <Alert>
        <CircleAlertIcon />
        <AlertTitle>{UNSUPPORTED_TITLE[slot]()}</AlertTitle>
        <AlertDescription>
          {intl.formatMessage({
            id: "models_download_image_unsupported_body",
            defaultMessage:
              "This build has no local image runtime. Use a server above instead.",
          })}
        </AlertDescription>
      </Alert>
    )
  }

  // A download does not block the rest: another one queues behind it.
  const busy = select.isPending || remove.isPending

  const act = (build: LocalBuild) => {
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
      {[...byFamily(catalog.data)].map(([family, rows]) => (
        <ModelFamilyGroup key={family} family={family}>
          {rows.map((row) => (
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
