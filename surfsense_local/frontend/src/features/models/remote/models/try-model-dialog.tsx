import { useEffect, useState } from "react"

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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Spinner } from "@/components/ui/spinner"
import { ApiError } from "@/lib/api"
import { intl } from "@/i18n/intl"

import type { ModelType } from "../../model-type"
import type { ModelSelection } from "../../selection/api"
import { useSelect } from "../../selection/use-selection"
import {
  testConnectionChat,
  testConnectionImage,
  type ConnectionModel,
} from "./api"

function messageFrom(error: unknown) {
  return error instanceof Error
    ? error.message
    : intl.formatMessage({
        id: "models_try_dialog_request_error",
        defaultMessage: "The request failed",
      })
}

function Explanation({
  modelType,
  model,
}: {
  modelType: ModelType
  model: ConnectionModel
}) {
  const image = modelType === "image_gen"
  if (model.capability_source === "unknown") {
    return image
      ? intl.formatMessage({
          id: "models_try_dialog_image_unconfirmed_body",
          defaultMessage:
            "This endpoint does not publish capabilities, so image support is unconfirmed. It must implement /images/generations or /images. Testing runs real inference and may cost money.",
        })
      : intl.formatMessage({
          id: "models_try_dialog_chat_unconfirmed_body",
          defaultMessage:
            "This endpoint does not publish capabilities, so chat support is unconfirmed. Testing sends one short prompt and may cost money.",
        })
  }
  return image
    ? intl.formatMessage({
        id: "models_try_dialog_image_confirmed_body",
        defaultMessage:
          "Image support is confirmed. Testing runs real inference and may cost money.",
      })
    : intl.formatMessage({
        id: "models_try_dialog_chat_confirmed_body",
        defaultMessage:
          "Chat support is confirmed. Testing sends one short prompt and may cost money.",
      })
}

/**
 * A server model on trial before it takes a slot. Testing is optional and may
 * cost money, so it is offered, never required. `unlisted` marks a hand-typed
 * id; a listed one still goes through the server's own check first.
 */
export function TryModelDialog({
  modelType,
  model,
  unlisted,
  onClose,
  onSelected,
}: {
  modelType: ModelType
  model: ConnectionModel
  unlisted: boolean
  onClose: () => void
  onSelected?: (selection: ModelSelection) => void
}) {
  const select = useSelect(modelType)
  const [testing, setTesting] = useState(false)
  const [reply, setReply] = useState<string | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [confirmUnlisted, setConfirmUnlisted] = useState<string | null>(null)

  useEffect(
    () => () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl)
    },
    [previewUrl]
  )

  const runTest = () => {
    setTesting(true)
    setError(null)
    const attempt =
      modelType === "image_gen"
        ? testConnectionImage(model.connection_id, model.name).then((blob) =>
            setPreviewUrl(URL.createObjectURL(blob))
          )
        : testConnectionChat(model.connection_id, model.name).then(setReply)
    void attempt
      .catch((cause: unknown) => setError(messageFrom(cause)))
      .finally(() => setTesting(false))
  }

  const assign = (allowUnlisted: boolean) => {
    setError(null)
    select
      .mutateAsync({
        target: {
          provider: "openai_compatible",
          connection_id: model.connection_id,
          name: model.name,
        },
        allowUnlisted,
      })
      .then((selection) => {
        onSelected?.(selection)
        onClose()
      })
      .catch((cause: unknown) => {
        if (
          !allowUnlisted &&
          cause instanceof ApiError &&
          cause.status === 422
        ) {
          setConfirmUnlisted(messageFrom(cause))
        } else {
          setError(messageFrom(cause))
        }
      })
  }

  return (
    <>
      <Dialog open onOpenChange={(open) => !open && onClose()}>
        <DialogContent className="select-none">
          <DialogHeader>
            <DialogTitle>
              {intl.formatMessage(
                {
                  id: "models_try_dialog_title",
                  defaultMessage:
                    "{slot, select, text_gen {Use {model} for chat?} image_gen {Use {model} for image?} image_edit {Use {model} for image editing?} video_gen {Use {model} for video?} audio_gen {Use {model} for audio?} other {Use {model}?}}",
                },
                {
                  slot: modelType,
                  model: model.name,
                }
              )}
            </DialogTitle>
            <DialogDescription>
              <Explanation modelType={modelType} model={model} />
            </DialogDescription>
          </DialogHeader>
          {previewUrl ? (
            <img
              src={previewUrl}
              alt={intl.formatMessage(
                {
                  id: "models_try_dialog_preview_aria",
                  defaultMessage: "Test generated by {model}",
                },
                {
                  model: model.name,
                }
              )}
              className="max-h-64 w-full rounded-md object-contain"
            />
          ) : null}
          {reply ? (
            <p className="max-h-48 overflow-y-auto rounded-md border bg-muted/40 p-3 text-sm whitespace-pre-wrap">
              {reply}
            </p>
          ) : null}
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          <DialogFooter>
            <Button variant="outline" onClick={onClose}>
              {intl.formatMessage({
                id: "models_try_dialog_cancel_button",
                defaultMessage: "Cancel",
              })}
            </Button>
            <Button variant="outline" disabled={testing} onClick={runTest}>
              {testing ? <Spinner data-icon="inline-start" /> : null}
              {modelType === "image_gen"
                ? intl.formatMessage({
                    id: "models_try_dialog_test_image_button",
                    defaultMessage: "Test image",
                  })
                : intl.formatMessage({
                    id: "models_try_dialog_test_chat_button",
                    defaultMessage: "Test chat",
                  })}
            </Button>
            <Button
              disabled={select.isPending}
              onClick={() => assign(unlisted)}
            >
              {select.isPending ? <Spinner data-icon="inline-start" /> : null}
              {previewUrl || reply
                ? intl.formatMessage({
                    id: "models_try_dialog_use_tested_button",
                    defaultMessage: "Use this model",
                  })
                : intl.formatMessage({
                    id: "models_try_dialog_use_untested_button",
                    defaultMessage: "Use without testing",
                  })}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={confirmUnlisted !== null}
        onOpenChange={(open) => !open && setConfirmUnlisted(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {intl.formatMessage({
                id: "models_try_dialog_unlisted_title",
                defaultMessage: "Use an unlisted model?",
              })}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {confirmUnlisted ? `${confirmUnlisted} ` : ""}
              {intl.formatMessage({
                id: "models_try_dialog_unlisted_body",
                defaultMessage:
                  "SurfSense could not confirm this model in the live catalogue. Continue only if the exact model ID is correct.",
              })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>
              {intl.formatMessage({
                id: "models_try_dialog_unlisted_cancel_button",
                defaultMessage: "Cancel",
              })}
            </AlertDialogCancel>
            <AlertDialogAction onClick={() => assign(true)}>
              {intl.formatMessage({
                id: "models_try_dialog_unlisted_confirm_button",
                defaultMessage: "Use unlisted model",
              })}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
