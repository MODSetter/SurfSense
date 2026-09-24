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
          <AlertDialogTitle>Delete {row?.name}?</AlertDialogTitle>
          <AlertDialogDescription>
            {row?.selected
              ? "This is your current model. Deleting it will require you to choose another model."
              : "This permanently removes the model and its downloaded data from this computer."}
          </AlertDialogDescription>
        </AlertDialogHeader>
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        <AlertDialogFooter>
          <AlertDialogCancel disabled={pending}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            disabled={pending}
            onClick={(event) => {
              event.preventDefault()
              onConfirm()
            }}
          >
            {pending ? <Spinner data-icon="inline-start" /> : null}
            {pending ? "Deleting…" : "Delete model"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
