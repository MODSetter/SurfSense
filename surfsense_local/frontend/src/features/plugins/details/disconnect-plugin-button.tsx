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

/** Disconnecting drops the key or sign-in, so it is confirmed first; the plugin stays to connect again. */
export function DisconnectPluginButton({
  name,
  disconnecting,
  onDisconnect,
}: {
  name: string
  disconnecting: boolean
  onDisconnect: () => void
}) {
  return (
    <AlertDialog>
      <AlertDialogTrigger
        render={
          <Button
            type="button"
            size="sm"
            variant="secondary"
            aria-label={intl.formatMessage(
              {
                id: "plugins_disconnect_trigger_aria",
                defaultMessage: "Disconnect {plugin}",
              },
              { plugin: name }
            )}
          >
            {intl.formatMessage({
              id: "plugins_disconnect_trigger_button",
              defaultMessage: "Disconnect",
            })}
          </Button>
        }
      />
      <AlertDialogContent className="select-none">
        <AlertDialogHeader>
          <AlertDialogTitle>
            {intl.formatMessage(
              {
                id: "plugins_disconnect_dialog_title",
                defaultMessage: "Disconnect {plugin}?",
              },
              { plugin: name }
            )}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {intl.formatMessage({
              id: "plugins_disconnect_dialog_body",
              defaultMessage:
                "The agent stops using it until you connect it again. Your tool settings are kept.",
            })}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>
            {intl.formatMessage({
              id: "plugins_disconnect_dialog_cancel_button",
              defaultMessage: "Cancel",
            })}
          </AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            disabled={disconnecting}
            onClick={onDisconnect}
          >
            {intl.formatMessage({
              id: "plugins_disconnect_dialog_confirm_button",
              defaultMessage: "Disconnect",
            })}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
