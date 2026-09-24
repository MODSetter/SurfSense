import { useSyncExternalStore } from "react"
import { toast } from "sonner"

import { useRefreshModels } from "../../models-query"
import type { ModelSelection } from "../../selection/api"
import { installCatalogModel, type InstallEvent } from "./api"

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

// Module state, not component state: a download outlives the view that started
// it, so leaving the catalog or closing settings does not cancel it.
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

function isAbort(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError"
}

function messageFrom(error: unknown) {
  return error instanceof Error ? error.message : "Could not install this model"
}

/**
 * One install at a time. Curated and searched builds go through the same
 * call, because the id is opaque either way. The server selects what it
 * installs, so a finished install is also a new chat model.
 */
export function useChatInstall(
  onSelected?: (selection: ModelSelection) => void
) {
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
        next.signal
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
