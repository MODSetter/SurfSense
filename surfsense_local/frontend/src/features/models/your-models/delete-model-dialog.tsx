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
              { id: "models_delete_dialog_title" },
              { model: row?.name ?? "" }
            )}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {row?.selected
              ? intl.formatMessage({ id: "models_delete_dialog_in_use_body" })
              : intl.formatMessage({ id: "models_delete_dialog_body" })}
          </AlertDialogDescription>
        </AlertDialogHeader>
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        <AlertDialogFooter>
          <AlertDialogCancel disabled={pending}>
            {intl.formatMessage({ id: "models_delete_dialog_cancel_button" })}
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
                })
              : intl.formatMessage({
                  id: "models_delete_dialog_confirm_button",
                })}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
