import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { intl } from "@/i18n/intl"

/** Removing deletes the plugin with its key and tool settings, so it is confirmed first. */
export function RemovePluginButton({
  name,
  removing,
  onRemove,
}: {
  name: string
  removing: boolean
  onRemove: () => void
}) {
  return (
    <AlertDialog>
      <AlertDialogTrigger
        render={
          <Button
            type="button"
            size="sm"
            variant="ghost"
            aria-label={intl.formatMessage(
              {
                id: "plugins_remove_trigger_aria",
                defaultMessage: "Remove {plugin}",
              },
              { plugin: name }
            )}
          >
            {intl.formatMessage({
              id: "plugins_remove_trigger_button",
              defaultMessage: "Remove",
            })}
          </Button>
        }
      />
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
