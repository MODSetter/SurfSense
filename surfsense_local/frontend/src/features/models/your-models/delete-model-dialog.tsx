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
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"

import { appName } from "../local/elsewhere/app-name"
import type { YourModelRow } from "./your-model-row"

export function DeleteModelDialog({
  open,
  row,
  pending,
  error,
  onConfirm,
  onOpenChange,
  onOpenChangeComplete,
}: {
  open: boolean
  row: YourModelRow | null
  pending: boolean
  error: string | null
  onConfirm: () => void
  onOpenChange: (open: boolean) => void
  /** Where the caller clears `row`, once the dialog has finished closing. */
  onOpenChangeComplete: (open: boolean) => void
}) {
  const keptBy = row?.keptBy ?? null
  return (
    <AlertDialog
      open={open}
      onOpenChange={(open) => {
        if (!pending) onOpenChange(open)
      }}
      onOpenChangeComplete={onOpenChangeComplete}
    >
      <AlertDialogContent className="select-none">
        <AlertDialogHeader>
          <AlertDialogTitle>
            {keptBy
              ? intl.formatMessage(
                  {
                    id: "models_delete_dialog_stop_using_title",
                    defaultMessage: "Stop using {model}?",
                  },
                  { model: row?.name ?? "" }
                )
              : intl.formatMessage(
                  {
                    id: "models_delete_dialog_title",
                    defaultMessage: "Delete {model}?",
                  },
                  { model: row?.name ?? "" }
                )}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {keptBy === "folder"
              ? intl.formatMessage({
                  id: "models_delete_dialog_stop_using_folder_body",
                  defaultMessage:
                    "SurfSense stops using this file and deletes nothing. It stays where it is.",
                })
              : keptBy
                ? intl.formatMessage(
                    {
                      id: "models_delete_dialog_stop_using_body",
                      defaultMessage:
                        "SurfSense stops using this file and deletes nothing. It stays where it is, in {app}.",
                    },
                    { app: appName(keptBy) }
                  )
                : row?.selected
                  ? intl.formatMessage({
                      id: "models_delete_dialog_in_use_body",
                      defaultMessage:
                        "This is your current model. Deleting it will require you to choose another model.",
                    })
                  : intl.formatMessage({
                      id: "models_delete_dialog_body",
                      defaultMessage:
                        "This permanently removes the model and its downloaded data from this computer.",
                    })}
          </AlertDialogDescription>
        </AlertDialogHeader>
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        <AlertDialogFooter>
          <AlertDialogCancel disabled={pending}>
            {intl.formatMessage({
              id: "models_delete_dialog_cancel_button",
              defaultMessage: "Cancel",
            })}
          </AlertDialogCancel>
          <AlertDialogAction
            variant={keptBy ? "default" : "destructive"}
            disabled={pending}
            onClick={(event) => {
              event.preventDefault()
              onConfirm()
            }}
          >
            {pending ? <Spinner data-icon="inline-start" /> : null}
            {keptBy
              ? intl.formatMessage({
                  id: "models_delete_dialog_stop_using_button",
                  defaultMessage: "Stop using",
                })
              : pending
                ? intl.formatMessage({
                    id: "models_delete_dialog_deleting_status",
                    defaultMessage: "Deleting…",
                  })
                : intl.formatMessage({
                    id: "models_delete_dialog_confirm_button",
                    defaultMessage: "Delete model",
                  })}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
