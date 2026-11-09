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
import { DotIcon } from "@/components/ui/icons"
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

function body({ kind, adopt }: MoveReady) {
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
    ? intl.formatMessage({
        id: "storage_move_confirm_models_body",
        defaultMessage:
          "SurfSense will copy your models and restart. The old copy is removed automatically. Local models won’t work while this drive is disconnected.",
      })
    : intl.formatMessage({
        id: "storage_move_confirm_data_body",
        defaultMessage:
          "SurfSense will copy your data and restart. The old copy is removed automatically. SurfSense won’t start unless this drive is connected.",
      })
}

/** One screen of a dialog, so a flow can arrive here without closing and reopening. */
export function MoveConfirmContent({
  ready,
  onConfirm,
}: {
  ready: MoveReady
  onConfirm: () => void
}) {
  return (
    <>
      <AlertDialogHeader>
        <AlertDialogTitle>{title(ready)}</AlertDialogTitle>
      </AlertDialogHeader>
      <div className="flex flex-col gap-3 text-sm">
        {ready.adopt ? null : (
          <div className="flex flex-col gap-0.5">
            <span className="text-muted-foreground">
              {intl.formatMessage({
                id: "storage_move_confirm_from_label",
                defaultMessage: "From",
              })}
            </span>
            <code className="break-all select-text">{ready.source}</code>
          </div>
        )}
        <div className="flex flex-col gap-0.5">
          <span className="text-muted-foreground">
            {intl.formatMessage({
              id: "storage_move_confirm_to_label",
              defaultMessage: "To",
            })}
          </span>
          <code className="break-all select-text">{ready.target}</code>
          {ready.adopt ? null : (
            <span className="flex flex-wrap items-center text-muted-foreground tabular-nums">
              {intl.formatMessage(
                {
                  id: "storage_move_confirm_space_label",
                  defaultMessage:
                    "Needs {needed, number, ::unit/gigabyte .#}<dot></dot>{free, number, ::unit/gigabyte .#} free",
                },
                {
                  needed: ready.neededBytes / 1e9,
                  free: ready.freeBytes / 1e9,
                  dot: () => (
                    <DotIcon key="dot" aria-hidden="true" className="size-3 shrink-0" />
                  ),
                }
              )}
            </span>
          )}
        </div>
      </div>
      <AlertDialogDescription>{body(ready)}</AlertDialogDescription>
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
      <AlertDialogContent className="select-none">
        {ready ? <MoveConfirmContent ready={ready} onConfirm={onConfirm} /> : null}
      </AlertDialogContent>
    </AlertDialog>
  )
}
