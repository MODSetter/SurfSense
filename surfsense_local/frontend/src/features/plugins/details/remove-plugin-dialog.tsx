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

/** Removing deletes the plugin with its key and tool settings, so it is confirmed first. Opened from the actions menu. */
export function RemovePluginDialog({
  name,
  open,
  onOpenChange,
  removing,
  onRemove,
}: {
  name: string
  open: boolean
  onOpenChange: (open: boolean) => void
  removing: boolean
  onRemove: () => void
}) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="select-none">
        <AlertDialogHeader>
          <AlertDialogTitle>
            {intl.formatMessage(
              {
                id: "plugins_remove_dialog_title",
                defaultMessage: "Remove {plugin}?",
              },
              { plugin: name }
            )}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {intl.formatMessage({
              id: "plugins_remove_dialog_body",
              defaultMessage: "This deletes it, its key and its tool settings.",
            })}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>
            {intl.formatMessage({
              id: "plugins_remove_dialog_cancel_button",
              defaultMessage: "Cancel",
            })}
          </AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            disabled={removing}
            onClick={onRemove}
          >
            {intl.formatMessage({
              id: "plugins_remove_dialog_confirm_button",
              defaultMessage: "Remove",
            })}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
