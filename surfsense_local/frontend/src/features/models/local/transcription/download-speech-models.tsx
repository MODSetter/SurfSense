import { Fragment, useState } from "react"

import { CircleAlertIcon, DotIcon, Trash2Icon } from "@/components/ui/icons"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { intl } from "@/i18n/intl"

import { useSelect } from "../../selection/use-selection"
import { DeleteModelDialog } from "../../your-models/delete-model-dialog"
import type { YourModelRow } from "../../your-models/your-model-row"
import { useInstall } from "../installs/use-install"
import { jobFor } from "../installs/job-state"
import { BuildAction } from "../chat/build-action"
import { InstallProgress } from "../chat/install-progress"
import type { LocalSpeechModel } from "./api"
import { describeSpeechModel } from "./describe-speech-model"
import { ListedLanguages } from "./listed-languages"
import { useDeleteLocalSpeechModel } from "./use-delete-local-speech-model"
import { useLocalSpeechCatalog } from "./use-local-speech-catalog"

function messageFrom(error: unknown) {
  return error instanceof Error
    ? error.message
    : intl.formatMessage({
        id: "models_download_speech_request_error",
        defaultMessage: "The request failed",
      })
}

/** The row `DeleteModelDialog` needs; it only reads `name` and `selected`. */
function deletableRow(model: LocalSpeechModel): YourModelRow | null {
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

/**
 * Speech recognition models audio.cpp can run on this computer. A download
 * becomes the model in use: one model serves recordings and voice input.
 */
export function DownloadSpeechModels() {
  const catalog = useLocalSpeechCatalog()
  const { installs, install, cancel } = useInstall({
    select: true,
    modelType: "speech_to_text",
  })
  const select = useSelect("speech_to_text")
  const remove = useDeleteLocalSpeechModel()
  const [deleting, setDeleting] = useState<YourModelRow | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  if (catalog.isPending) return null

  if (catalog.isError) {
    return (
      <Alert variant="destructive">
        <CircleAlertIcon />
        <AlertTitle>
          {intl.formatMessage({
            id: "models_download_speech_load_error",
            defaultMessage: "Could not load speech recognition models",
          })}
        </AlertTitle>
        <AlertDescription>{messageFrom(catalog.error)}</AlertDescription>
      </Alert>
    )
  }

  const models = catalog.data
  if (models.length === 0) {
    return (
      <Alert>
        <CircleAlertIcon />
        <AlertTitle>
          {intl.formatMessage({
            id: "models_download_speech_unsupported_title",
            defaultMessage:
              "Speech recognition models cannot run on this computer",
          })}
        </AlertTitle>
      </Alert>
    )
  }

  // A download does not block the rest: another one queues behind it.
  const busy = select.isPending || remove.isPending

  const act = (model: LocalSpeechModel) => {
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
      void install(model.catalog_id)
    }
  }

  const confirmDelete = () => {
    if (!deleting?.removeId) return
    setDeleteError(null)
    remove
      .mutateAsync(deleting.removeId)
      .then(() => setDeleteOpen(false))
      .catch((cause: unknown) => setDeleteError(messageFrom(cause)))
  }

  return (
    <div className="flex flex-col gap-3">
      <ul className="divide-y overflow-hidden rounded-xl border bg-card">
        {models.map((model) => {
          const job = jobFor(installs, model.catalog_id)
          return (
            <li key={model.id} className="flex flex-col gap-2 px-3 py-2.5">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{model.label}</p>
                  <p className="flex flex-wrap items-center text-xs text-muted-foreground tabular-nums">
                    {describeSpeechModel(model).map((fact, index) => (
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
                    installs={installs}
                    disabled={busy}
                    onAction={() => act(model)}
                  />
                  {model.installed_as ? (
                    <Button
                      type="button"
                      size="icon-sm"
                      variant="destructive"
                      // The API refuses a delete while any install runs.
                      disabled={busy || installs.length > 0}
                      aria-label={intl.formatMessage(
                        {
                          id: "models_download_speech_delete_aria",
                          defaultMessage: "Delete {model}",
                        },
                        { model: model.label }
                      )}
                      onClick={() => {
                        setDeleteError(null)
                        setDeleting(deletableRow(model))
                        setDeleteOpen(true)
                      }}
                    >
                      <Trash2Icon />
                    </Button>
                  ) : null}
                </div>
              </div>
              <ListedLanguages codes={model.languages} />
              {job ? (
                <InstallProgress
                  event={job.event}
                  onCancel={() => cancel(job.id)}
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
        open={deleteOpen}
        row={deleting}
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
