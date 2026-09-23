import { useSyncExternalStore } from "react"

import { useRefreshModels } from "../../models-query"
import { installLocalImageModel, type DownloadStep } from "./api"

export type ImageInstallState =
  | { status: "idle"; error: string | null }
  | { status: "installing"; name: string; label: string; step: DownloadStep }

// Module state, as with chat installs: a download outlives the view that
// started it.
let state: ImageInstallState = { status: "idle", error: null }
let controller: AbortController | null = null
const listeners = new Set<() => void>()

function publish(next: ImageInstallState) {
  state = next
  for (const listener of listeners) listener()
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function messageFrom(error: unknown) {
  return error instanceof Error ? error.message : "The download failed"
}

/** Downloading does not select: an image model is picked once it is on disk. */
export function useImageInstall() {
  const installState = useSyncExternalStore(subscribe, () => state)
  const refresh = useRefreshModels()

  const install = async (model: {
    name: string
    label: string
    size_bytes: number
  }) => {
    if (state.status === "installing") return
    const next = new AbortController()
    controller = next
    const progress = (step: DownloadStep) =>
      publish({
        status: "installing",
        name: model.name,
        label: model.label,
        step,
      })
    progress({ status: "starting", completed: 0, total: model.size_bytes })
    let error: string | null = null
    try {
      await installLocalImageModel(model.name, progress, next.signal)
    } catch (cause) {
      if (!next.signal.aborted) error = messageFrom(cause)
    } finally {
      controller = null
      await refresh()
      publish({ status: "idle", error })
    }
  }

  return {
    installState,
    install,
    cancelInstall: () => controller?.abort(),
  }
}
