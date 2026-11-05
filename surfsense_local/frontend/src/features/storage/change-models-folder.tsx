import { useState } from "react"

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"

import { MoveConfirmContent } from "./move-confirm-dialog"
import { useMoveFlow } from "./use-move-flow"
import { useStorageState } from "./use-storage-state"

/**
 * A quiet link beside the model list. Choosing before the first download costs
 * almost nothing, and the folder itself only matters once someone asks.
 */
export function ChangeModelsFolder() {
  const { data: state } = useStorageState()
  const flow = useMoveFlow()
  const [open, setOpen] = useState(false)
  if (!state?.models.connected) return null

  const { path, freeBytes } = state.models
  const close = () => {
    setOpen(false)
    flow.dismiss()
  }

  return (
    <>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="text-muted-foreground"
        onClick={() => setOpen(true)}
      >
        {intl.formatMessage({
          id: "storage_onboarding_change_link",
          defaultMessage: "Change download folder",
        })}
      </Button>
      <AlertDialog
        open={open}
        onOpenChange={(next) => {
          if (!next) close()
        }}
      >
        <AlertDialogContent className="select-none">
          {flow.ready ? (
            <MoveConfirmContent
              ready={flow.ready}
              onConfirm={() => {
                setOpen(false)
                flow.confirm()
              }}
            />
          ) : (
            <>
              <AlertDialogHeader>
                <AlertDialogTitle>
                  {intl.formatMessage({
                    id: "storage_models_folder_title",
                    defaultMessage: "Models folder",
                  })}
                </AlertDialogTitle>
                <AlertDialogDescription>
                  {intl.formatMessage({
                    id: "storage_models_folder_body",
                    defaultMessage:
                      "Where SurfSense keeps the models you download.",
                  })}
                </AlertDialogDescription>
              </AlertDialogHeader>
              <div className="flex flex-col gap-0.5 text-sm">
                <span className="text-muted-foreground">
                  {intl.formatMessage({
                    id: "storage_models_folder_current_label",
                    defaultMessage: "Current folder",
                  })}
                </span>
                <code className="break-all select-text">{path}</code>
                {freeBytes === null ? null : (
                  <span className="text-muted-foreground tabular-nums">
                    {intl.formatMessage(
                      {
                        id: "storage_models_folder_free_label",
                        defaultMessage:
                          "{free, number, ::unit/gigabyte .#} free on this drive",
                      },
                      { free: freeBytes / 1e9 }
                    )}
                  </span>
                )}
              </div>
              <AlertDialogFooter>
                <AlertDialogCancel>
                  {intl.formatMessage({
                    id: "storage_models_folder_cancel_button",
                    defaultMessage: "Cancel",
                  })}
                </AlertDialogCancel>
                <Button
                  type="button"
                  disabled={flow.planning !== null}
                  onClick={() => flow.choose("models")}
                >
                  {flow.planning ? <Spinner data-icon="inline-start" /> : null}
                  {intl.formatMessage({
                    id: "storage_models_folder_choose_button",
                    defaultMessage: "Choose folder…",
                  })}
                </Button>
              </AlertDialogFooter>
            </>
          )}
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
