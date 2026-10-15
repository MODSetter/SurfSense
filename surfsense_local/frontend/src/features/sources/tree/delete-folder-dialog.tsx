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
import { intl } from "@/i18n/intl"

/** A folder about to go, with how many sources and filed outputs go with it. */
export type FolderDeleteTarget = {
  id: number
  name: string
  sources: number
  artifacts: number
}

// Deleting is permanent until the Trash lands, so the dialog names the count.
export function DeleteFolderDialog({
  target,
  open,
  onOpenChange,
  onOpenChangeComplete,
  onDelete,
}: {
  target: FolderDeleteTarget | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onOpenChangeComplete: (open: boolean) => void
  onDelete: (folderId: number) => void
}) {
  return (
    <AlertDialog
      open={open}
      onOpenChange={onOpenChange}
      onOpenChangeComplete={onOpenChangeComplete}
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>
            {intl.formatMessage(
              {
                id: "sources_folder_delete_dialog_title",
                defaultMessage: "Delete {name}?",
              },
              { name: target?.name ?? "" }
            )}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {intl.formatMessage(
              {
                id: "sources_folder_delete_dialog_body",
                defaultMessage:
                  "{count, plural, =0 {This deletes the folder and the folders in it. It holds no sources.} one {This permanently deletes the folder, the # source in it and its indexed data.} other {This permanently deletes the folder, the # sources in it and their indexed data.}}",
              },
              { count: target?.sources ?? 0 }
            )}
            {target && target.artifacts > 0
              ? ` ${intl.formatMessage(
                  {
                    id: "sources_folder_delete_dialog_artifacts_body",
                    defaultMessage:
                      "{count, plural, one {It also deletes the # Studio output filed in it.} other {It also deletes the # Studio outputs filed in it.}}",
                  },
                  { count: target.artifacts }
                )}`
              : null}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>
            {intl.formatMessage({
              id: "sources_folder_delete_dialog_cancel_button",
              defaultMessage: "Cancel",
            })}
          </AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            onClick={() => {
              if (target) onDelete(target.id)
            }}
          >
            {intl.formatMessage(
              {
                id: "sources_folder_delete_dialog_confirm_button",
                defaultMessage:
                  "{count, plural, =0 {Delete folder} one {Delete folder and # source} other {Delete folder and # sources}}",
              },
              { count: target?.sources ?? 0 }
            )}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
