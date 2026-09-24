import { Fragment, useState } from "react"

import { CircleAlertIcon, DotIcon, Trash2Icon } from "@/components/ui/icons"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { intl } from "@/i18n/intl"

import { useSelect } from "../../selection/use-selection"
import { DeleteModelDialog } from "../../your-models/delete-model-dialog"
import type { YourModelRow } from "../../your-models/your-model-row"
import { BuildAction } from "../chat/build-action"
import { InstallProgress } from "../chat/install-progress"
import type { LocalAudioModel } from "./api"
import { describeAudioModel } from "./describe-audio-model"
import { useAudioInstall } from "./use-audio-install"
import { useDeleteLocalAudioModel } from "./use-delete-local-audio-model"
import { useLocalAudioCatalog } from "./use-local-audio-catalog"

function messageFrom(error: unknown) {
  return error instanceof Error
    ? error.message
    : intl.formatMessage({
        id: "models_download_audio_request_error",
        defaultMessage: "The request failed",
      })
}

/** The row `DeleteModelDialog` needs; it only reads `name` and `selected`. */
function deletableRow(model: LocalAudioModel): YourModelRow | null {
  if (!model.installed_as) return null
  return {
    key: model.installed_as,
    name: model.label,
    selected: model.selected,
    badges: [],
    note: null,
    target: null,
    removeId: model.installed_as,
  }
}

/** Audio models audio.cpp can run on this computer, with chat's and image's actions. */
export function DownloadAudioModels() {
  const catalog = useLocalAudioCatalog()
  const { installState, install, cancelInstall } = useAudioInstall()
  const select = useSelect("audio_gen")
  const remove = useDeleteLocalAudioModel()
  const [deleting, setDeleting] = useState<YourModelRow | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  if (catalog.isPending) return null

  if (catalog.isError) {
    return (
      <Alert variant="destructive">
        <CircleAlertIcon />
        <AlertTitle>
          {intl.formatMessage({
            id: "models_download_audio_load_error",
            defaultMessage: "Could not load local audio models",
          })}
        </AlertTitle>
        <AlertDescription>{messageFrom(catalog.error)}</AlertDescription>
      </Alert>
    )
  }

  const models = catalog.data.models
  if (models.length === 0) {
    return (
      <Alert>
        <CircleAlertIcon />
        <AlertTitle>
          {intl.formatMessage({
            id: "models_download_audio_unsupported_title",
            defaultMessage: "Audio models cannot run on this computer",
          })}
        </AlertTitle>
        <AlertDescription>
          {intl.formatMessage({
            id: "models_download_audio_unsupported_body",
            defaultMessage:
              "This build has no local audio runtime. Use a server above instead.",
          })}
        </AlertDescription>
      </Alert>
    )
  }

  const busy =
    installState.status === "installing" || select.isPending || remove.isPending

  const act = (model: LocalAudioModel) => {
    if (busy) return
    if (model.installed_as) {
      void select
        .mutateAsync({
          target: {
            provider: "audiocpp",
            connection_id: null,
            name: model.installed_as,
          },
        })
        .catch(() => undefined)
    } else {
      void install(model.catalog_id, model.label)
    }
  }

  const confirmDelete = () => {
    if (!deleting?.removeId) return
    setDeleteError(null)
    remove
      .mutateAsync(deleting.removeId)
      .then(() => setDeleting(null))
      .catch((cause: unknown) => setDeleteError(messageFrom(cause)))
  }

  return (
    <div className="flex flex-col gap-3">
      <ul className="divide-y overflow-hidden rounded-xl border bg-card">
        {models.map((model) => {
          const active =
            installState.status === "installing" &&
            installState.catalogId === model.catalog_id
          return (
            <li key={model.id} className="flex flex-col gap-2 px-3 py-2.5">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{model.label}</p>
                  <p className="flex flex-wrap items-center text-xs text-muted-foreground tabular-nums">
                    {describeAudioModel(model).map((fact, index) => (
                      <Fragment key={fact}>
                        {index > 0 ? (
                          <DotIcon
                            aria-hidden="true"
                            className="size-3 shrink-0"
                          />
                        ) : null}
                        <span>{fact}</span>
                      </Fragment>
                    ))}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <BuildAction
                    build={model.build}
                    label={model.label}
                    installState={installState}
                    disabled={busy}
                    runtimeAvailable
                    onAction={() => act(model)}
                  />
                  {model.installed_as ? (
                    <Button
                      type="button"
                      size="icon-sm"
                      variant="destructive"
                      disabled={busy}
                      aria-label={intl.formatMessage(
                        {
                          id: "models_download_audio_delete_aria",
                          defaultMessage: "Delete {model}",
                        },
                        {
                          model: model.label,
                        }
                      )}
                      onClick={() => {
                        setDeleteError(null)
                        setDeleting(deletableRow(model))
                      }}
                    >
                      <Trash2Icon />
                    </Button>
                  ) : null}
                </div>
              </div>
              {active ? (
                <InstallProgress
                  event={installState.event}
                  onCancel={cancelInstall}
                />
              ) : null}
            </li>
          )
        })}
      </ul>

      {select.isError ? (
        <p className="text-sm text-destructive">{messageFrom(select.error)}</p>
      ) : null}

      <DeleteModelDialog
        row={deleting}
        pending={remove.isPending}
        error={deleteError}
        onConfirm={confirmDelete}
        onCancel={() => setDeleting(null)}
      />
    </div>
  )
}
