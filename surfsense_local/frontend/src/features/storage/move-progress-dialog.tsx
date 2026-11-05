import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { intl } from "@/i18n/intl"

import { useMoveProgress } from "./move-progress-state"
import { moveFailureText } from "./refusal-text"
import type { MoveProgress } from "./storage-types"

function statusText(progress: MoveProgress) {
  switch (progress.phase) {
    case "copying":
      return intl.formatMessage({
        id: "storage_move_progress_copying_status",
        defaultMessage: "Copying your files…",
      })
    case "verifying":
      return intl.formatMessage({
        id: "storage_move_progress_verifying_status",
        defaultMessage: "Checking the copy…",
      })
    case "switching":
      return intl.formatMessage({
        id: "storage_move_progress_switching_status",
        defaultMessage: "Finishing up…",
      })
    default:
      return intl.formatMessage({
        id: "storage_move_progress_stopping_status",
        defaultMessage: "Getting ready…",
      })
  }
}

/** Over everything, since a move stops the API the rest of the page depends on. */
export function MoveProgressDialog() {
  const progress = useMoveProgress()
  const bridge = window.surfsense?.storage
  if (progress === null) return null

  if (progress.phase === "failed") {
    return (
      <AlertDialog open>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {intl.formatMessage({
                id: "storage_move_failed_title",
                defaultMessage: "Your files weren’t moved",
              })}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {moveFailureText(progress.reason)}{" "}
              {intl.formatMessage({
                id: "storage_move_failed_body",
                defaultMessage:
                  "Nothing was lost: SurfSense keeps using the folder it had.",
              })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <Button type="button" onClick={() => void bridge?.restart()}>
              {intl.formatMessage({
                id: "storage_move_failed_restart_button",
                defaultMessage: "Restart SurfSense",
              })}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    )
  }

  const fraction =
    progress.phase === "stopping" || progress.totalBytes === 0
      ? 0
      : progress.doneBytes / progress.totalBytes
  const cancellable = progress.phase === "copying" || progress.phase === "verifying"

  return (
    <AlertDialog open>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>
            {intl.formatMessage({
              id: "storage_move_progress_title",
              defaultMessage: "Moving your files",
            })}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {intl.formatMessage({
              id: "storage_move_progress_body",
              defaultMessage:
                "Keep SurfSense open. It restarts when the move is done.",
            })}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="flex flex-col gap-2">
          <Progress value={fraction * 100} />
          <p className="flex justify-between gap-4 text-sm text-muted-foreground">
            <span>{statusText(progress)}</span>
            <span className="tabular-nums">
              {intl.formatNumber(fraction, { style: "percent" })}
            </span>
          </p>
        </div>
        {cancellable ? (
          <AlertDialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => void bridge?.cancel()}
            >
              {intl.formatMessage({
                id: "storage_move_progress_cancel_button",
                defaultMessage: "Cancel",
              })}
            </Button>
          </AlertDialogFooter>
        ) : null}
      </AlertDialogContent>
    </AlertDialog>
  )
}
