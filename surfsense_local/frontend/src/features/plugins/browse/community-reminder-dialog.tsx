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

/**
 * Asked before a community plugin connects: SurfSense has not proven its author runs
 * the service it connects to, and everything sent to it passes through their server.
 */
export function CommunityReminderDialog({
  plugin,
  author,
  open,
  onOpenChange,
  onConnect,
}: {
  plugin: string
  author: string
  open: boolean
  onOpenChange: (open: boolean) => void
  onConnect: () => void
}) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="select-none">
        <AlertDialogHeader>
          <AlertDialogTitle>
            {intl.formatMessage(
              {
                id: "plugins_community_reminder_title",
                defaultMessage: "Connect {plugin}?",
              },
              { plugin }
            )}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {intl.formatMessage(
              {
                id: "plugins_community_reminder_body",
                defaultMessage:
                  "{plugin} isn’t verified by SurfSense. Your requests and sign-in go to {author}’s server, so only connect it if you trust {author}.",
              },
              { plugin, author }
            )}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>
            {intl.formatMessage({
              id: "plugins_community_reminder_cancel_button",
              defaultMessage: "Cancel",
            })}
          </AlertDialogCancel>
          <AlertDialogAction onClick={onConnect}>
            {intl.formatMessage({
              id: "plugins_community_reminder_connect_button",
              defaultMessage: "Connect",
            })}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
