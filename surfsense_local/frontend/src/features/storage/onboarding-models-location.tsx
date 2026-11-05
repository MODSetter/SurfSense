import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"

import { MoveConfirmDialog } from "./move-confirm-dialog"
import { useMoveFlow } from "./use-move-flow"
import { useStorageState } from "./use-storage-state"

/**
 * One line, not a step: most people never touch it. Choosing here costs almost
 * nothing, before any model has been downloaded to the wrong drive.
 */
export function OnboardingModelsLocation({ neededBytes }: { neededBytes?: number }) {
  const { data: state } = useStorageState()
  const flow = useMoveFlow()
  if (!state?.models.connected) return null

  const { path, freeBytes } = state.models
  const tight =
    neededBytes !== undefined && freeBytes !== null && freeBytes < neededBytes

  return (
    <div className="flex items-center justify-between gap-4 text-xs">
      <p className={tight ? "min-w-0 text-destructive" : "min-w-0 text-muted-foreground"}>
        {freeBytes === null
          ? intl.formatMessage(
              {
                id: "storage_onboarding_location_label",
                defaultMessage: "Models save to {path}",
              },
              { path }
            )
          : intl.formatMessage(
              {
                id: "storage_onboarding_location_free_label",
                defaultMessage:
                  "Models save to {path} · {free, number, ::unit/gigabyte .#} free",
              },
              { path, free: freeBytes / 1e9 }
            )}
      </p>
      <Button
        type="button"
        variant={tight ? "outline" : "ghost"}
        size="sm"
        className="shrink-0"
        disabled={flow.planning !== null}
        onClick={() => flow.choose("models")}
      >
        {flow.planning ? <Spinner data-icon="inline-start" /> : null}
        {intl.formatMessage({
          id: "storage_onboarding_change_button",
          defaultMessage: "Change",
        })}
      </Button>
      <MoveConfirmDialog
        ready={flow.ready}
        onConfirm={flow.confirm}
        onDismiss={flow.dismiss}
      />
    </div>
  )
}
