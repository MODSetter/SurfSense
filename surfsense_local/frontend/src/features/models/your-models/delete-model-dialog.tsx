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

import type { YourModelRow } from "./your-model-row"

export function DeleteModelDialog({
  row,
  pending,
  error,
  onConfirm,
  onCancel,
}: {
  row: YourModelRow | null
  pending: boolean
  error: string | null
  onConfirm: () => void
  onCancel: () => void
}) {
  return (
    <AlertDialog
      open={row !== null}
      onOpenChange={(open) => {
        if (!open && !pending) onCancel()
      }}
    >
      <AlertDialogContent className="select-none">
        <AlertDialogHeader>
          <AlertDialogTitle>
            {intl.formatMessage(
              {
                id: "models_delete_dialog_title",
                defaultMessage: "Delete {model}?",
              },
              { model: row?.name ?? "" }
            )}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {row?.selected
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
            variant="destructive"
            disabled={pending}
            onClick={(event) => {
              event.preventDefault()
              onConfirm()
            }}
          >
            {pending ? <Spinner data-icon="inline-start" /> : null}
            {pending
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
