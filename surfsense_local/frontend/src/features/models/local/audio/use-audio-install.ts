import { useSyncExternalStore } from "react"

import { useRefreshModels } from "../../models-query"
import { installLocalAudioModel, type DownloadStep } from "./api"

export type AudioInstallState =
  | { status: "idle"; error: string | null }
  | { status: "installing"; id: string; label: string; step: DownloadStep }

// Module state, as with chat and image installs: a download outlives the view
// that started it.
let state: AudioInstallState = { status: "idle", error: null }
let controller: AbortController | null = null
const listeners = new Set<() => void>()

function publish(next: AudioInstallState) {
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

/** Downloading does not select: an audio model is picked once it is on disk. */
export function useAudioInstall() {
  const installState = useSyncExternalStore(subscribe, () => state)
  const refresh = useRefreshModels()

  const install = async (model: {
    id: string
    catalog_id: string
    label: string
    size_bytes: number
  }) => {
    if (state.status === "installing") return
    const next = new AbortController()
    controller = next
    const progress = (step: DownloadStep) =>
      publish({
        status: "installing",
        id: model.id,
        label: model.label,
        step,
      })
    progress({ status: "starting", completed: 0, total: model.size_bytes })
    let error: string | null = null
    try {
      await installLocalAudioModel(model.catalog_id, progress, next.signal)
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
