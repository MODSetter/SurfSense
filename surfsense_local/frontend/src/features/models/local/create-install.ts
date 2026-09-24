import { useSyncExternalStore } from "react"
import { toast } from "sonner"

import { useRefreshModels } from "../models-query"
import type { ModelSelection } from "../selection/api"
import { installCatalogModel, type InstallEvent } from "./chat/api"

export type InstallState =
  | { status: "idle" }
  | {
      status: "installing"
      catalogId: string
      /** What the list calls it while it downloads. */
      label: string
      event: InstallEvent
    }

const IDLE: InstallState = { status: "idle" }

function isAbort(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError"
}

function messageFrom(error: unknown) {
  return error instanceof Error ? error.message : "Could not install this model"
}

/**
 * One install hook per model section, so chat and image show the same states
 * and each section shows only its own download. `select` is whether a finished
 * install also becomes the model in use: chat's does, image's waits for Use.
 */
export function createInstall({ select }: { select: boolean }) {
  // Module state, not component state: a download outlives the view that
  // started it, so leaving the catalog or closing settings does not cancel it.
  let state: InstallState = IDLE
  let controller: AbortController | null = null
  const listeners = new Set<() => void>()

  function publish(next: InstallState) {
    state = next
    for (const listener of listeners) listener()
  }

  function subscribe(listener: () => void) {
    listeners.add(listener)
    return () => listeners.delete(listener)
  }

  return function useInstall(onSelected?: (selection: ModelSelection) => void) {
    const installState = useSyncExternalStore(subscribe, () => state)
    const refresh = useRefreshModels()

    const install = async (catalogId: string, label: string) => {
      if (state.status === "installing") return
      const next = new AbortController()
      controller = next
      publish({
        status: "installing",
        catalogId,
        label,
        event: { type: "starting", message: "Preparing download" },
      })
      try {
        const selection = await installCatalogModel(
          catalogId,
          (event) => publish({ status: "installing", catalogId, label, event }),
          next.signal,
          select
        )
        await refresh()
        if (selection) onSelected?.(selection)
      } catch (error) {
        if (isAbort(error)) {
          toast.info("Installation cancelled. You can retry.", {
            id: "model-install-cancelled",
          })
        } else {
          toast.error(messageFrom(error), { id: "model-install-error" })
        }
      } finally {
        controller = null
        publish(IDLE)
      }
    }

    return {
      installState,
      install,
      cancelInstall: () => controller?.abort(),
    }
  }
}
