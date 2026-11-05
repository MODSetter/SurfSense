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

import type { MoveReady } from "./storage-types"

function title({ kind }: MoveReady) {
  return kind === "models"
    ? intl.formatMessage({
        id: "storage_move_confirm_models_title",
        defaultMessage: "Move your models?",
      })
    : intl.formatMessage({
        id: "storage_move_confirm_data_title",
        defaultMessage: "Move all your data?",
      })
}

function body({ kind, adopt, neededBytes, freeBytes }: MoveReady) {
  if (adopt) {
    return kind === "models"
      ? intl.formatMessage({
          id: "storage_move_confirm_models_adopt_body",
          defaultMessage:
            "This folder already holds SurfSense models. SurfSense will restart and use them. Your current models stay where they are.",
        })
      : intl.formatMessage({
          id: "storage_move_confirm_data_adopt_body",
          defaultMessage:
            "This folder already holds SurfSense data. SurfSense will restart and use it. Your current data stays where it is.",
        })
  }
  return kind === "models"
    ? intl.formatMessage(
        {
          id: "storage_move_confirm_models_body",
          defaultMessage:
            "SurfSense will copy your models here, check the copy and restart, then delete the old copy. This needs {needed, number, ::unit/gigabyte .#} free; the drive has {free, number, ::unit/gigabyte .#}. Local models won’t work while this drive is disconnected.",
        },
        { needed: neededBytes / 1e9, free: freeBytes / 1e9 }
      )
    : intl.formatMessage(
        {
          id: "storage_move_confirm_data_body",
          defaultMessage:
            "SurfSense will copy your data here, check the copy and restart, then delete the old copy. This needs {needed, number, ::unit/gigabyte .#} free; the drive has {free, number, ::unit/gigabyte .#}. SurfSense won’t start unless this drive is connected.",
        },
        { needed: neededBytes / 1e9, free: freeBytes / 1e9 }
      )
}

export function MoveConfirmDialog({
  ready,
  onConfirm,
  onDismiss,
}: {
  ready: MoveReady | null
  onConfirm: () => void
  onDismiss: () => void
}) {
  return (
    <AlertDialog
      open={ready !== null}
      onOpenChange={(open) => {
        if (!open) onDismiss()
      }}
    >
      <AlertDialogContent>
        {ready ? (
          <>
            <AlertDialogHeader className="select-none">
              <AlertDialogTitle>{title(ready)}</AlertDialogTitle>
              <AlertDialogDescription>{body(ready)}</AlertDialogDescription>
            </AlertDialogHeader>
            <code className="text-sm break-all">{ready.target}</code>
            <AlertDialogFooter>
              <AlertDialogCancel>
                {intl.formatMessage({
                  id: "storage_move_confirm_cancel_button",
                  defaultMessage: "Cancel",
                })}
              </AlertDialogCancel>
              <AlertDialogAction onClick={onConfirm}>
                {ready.adopt
                  ? intl.formatMessage({
                      id: "storage_move_confirm_adopt_button",
                      defaultMessage: "Switch and restart",
                    })
                  : intl.formatMessage({
                      id: "storage_move_confirm_button",
                      defaultMessage: "Move and restart",
                    })}
              </AlertDialogAction>
            </AlertDialogFooter>
          </>
        ) : null}
      </AlertDialogContent>
    </AlertDialog>
  )
}
