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

import { useSelection } from "../../selection/use-selection"
import type { Connection } from "./api"
import { useDeleteConnection } from "./use-connections"

function messageFrom(error: unknown) {
  return error instanceof Error ? error.message : "Could not disconnect"
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
  const cleared = [
    chat.data?.connection_id === connection.id ? "Chat" : null,
    image.data?.connection_id === connection.id ? "Image" : null,
  ].filter(Boolean)

  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button
          type="button"
          size="sm"
          variant="destructive"
          disabled={disabled}
          aria-label={`Disconnect ${connection.label}`}
        >
          Disconnect
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent className="select-none">
        <AlertDialogHeader>
          <AlertDialogTitle>Disconnect {connection.label}?</AlertDialogTitle>
          <AlertDialogDescription>
            {cleared.length
              ? `Your ${cleared.join(" and ")} model${cleared.length > 1 ? "s" : ""} will be cleared.`
              : `No model in use comes from ${connection.label}.`}
          </AlertDialogDescription>
        </AlertDialogHeader>
        {remove.isError ? (
          <p className="text-sm text-destructive">
            {messageFrom(remove.error)}
          </p>
        ) : null}
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            disabled={remove.isPending}
            onClick={() => {
              // mutateAsync, not mutate's onSuccess: the refresh removes this
              // row, and a per-call callback is dropped once it unmounts.
              const clearsChat = chat.data?.connection_id === connection.id
              void remove
                .mutateAsync(connection.id)
                .then(() => {
                  if (clearsChat) onChatCleared?.()
                })
                .catch(() => undefined)
            }}
          >
            Disconnect
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
