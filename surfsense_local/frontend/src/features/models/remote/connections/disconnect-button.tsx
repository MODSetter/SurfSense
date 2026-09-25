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

import { useSelection } from "../../selection/use-selection"
import type { Connection } from "./api"
import { useDeleteConnection } from "./use-connections"

function messageFrom(error: unknown) {
  return error instanceof Error
    ? error.message
    : intl.formatMessage({
        id: "models_disconnect_error",
        defaultMessage: "Could not disconnect",
      })
}

/**
 * One connection serves every slot, so disconnecting it from the Chat section
 * can clear the Image model too. The confirmation names each slot it will clear.
 */
export function DisconnectButton({
  connection,
  disabled,
  onChatCleared,
}: {
  connection: Connection
  disabled: boolean
  onChatCleared?: () => void
}) {
  const chat = useSelection("text_gen")
  const image = useSelection("image_gen")
  const remove = useDeleteConnection()
  const clearsChatSlot = chat.data?.connection_id === connection.id
  const clearsImageSlot = image.data?.connection_id === connection.id
  const clearedBody =
    clearsChatSlot && clearsImageSlot
      ? intl.formatMessage({
          id: "models_disconnect_dialog_clears_both_body",
          defaultMessage: "Your Chat and Image models will be cleared.",
        })
      : clearsChatSlot
        ? intl.formatMessage({
            id: "models_disconnect_dialog_clears_chat_body",
            defaultMessage: "Your Chat model will be cleared.",
          })
        : clearsImageSlot
          ? intl.formatMessage({
              id: "models_disconnect_dialog_clears_image_body",
              defaultMessage: "Your Image model will be cleared.",
            })
          : intl.formatMessage(
              {
                id: "models_disconnect_dialog_clears_none_body",
                defaultMessage: "No model in use comes from {server}.",
              },
              {
                server: connection.label,
              }
            )

  return (
    <AlertDialog>
      <AlertDialogTrigger
        render={
          <Button
            type="button"
            size="sm"
            variant="destructive"
            disabled={disabled}
            aria-label={intl.formatMessage(
              {
                id: "models_disconnect_trigger_aria",
                defaultMessage: "Disconnect {server}",
              },
              {
                server: connection.label,
              }
            )}
          >
            {intl.formatMessage({
              id: "models_disconnect_trigger_button",
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
                id: "models_disconnect_dialog_title",
                defaultMessage: "Disconnect {server}?",
              },
              {
                server: connection.label,
              }
            )}
          </AlertDialogTitle>
          <AlertDialogDescription>{clearedBody}</AlertDialogDescription>
        </AlertDialogHeader>
        {remove.isError ? (
          <p className="text-sm text-destructive">
            {messageFrom(remove.error)}
          </p>
        ) : null}
        <AlertDialogFooter>
          <AlertDialogCancel>
            {intl.formatMessage({
              id: "models_disconnect_dialog_cancel_button",
              defaultMessage: "Cancel",
            })}
          </AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            disabled={remove.isPending}
            onClick={() => {
              // mutateAsync, not mutate's onSuccess: the refresh removes this
              // row, and a per-call callback is dropped once it unmounts.
              void remove
                .mutateAsync(connection.id)
                .then(() => {
                  if (clearsChatSlot) onChatCleared?.()
                })
                .catch(() => undefined)
            }}
          >
            {intl.formatMessage({
              id: "models_disconnect_dialog_confirm_button",
              defaultMessage: "Disconnect",
            })}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
