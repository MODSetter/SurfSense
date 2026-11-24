import { useState } from "react"

import { errorToast } from "@/features/feedback/error-toast"
import { intl } from "@/i18n/intl"
import { ApiError } from "@/lib/api"

import type { LocalRow } from "../chat/api"
import { offerFile } from "./api"
import { unusableReason } from "./unusable-text"
import { useElsewhereSettings } from "./use-elsewhere"

export type PickKind = "file" | "folder"

/**
 * The system's own dialog, for a model no look found. A file comes back as a
 * row to use; a folder is looked in from then on. Absent outside Electron: the
 * Docker image's browser cannot name a path on the server.
 */
export function usePickModel(onOffered: (row: LocalRow) => void) {
  const bridge =
    typeof window !== "undefined" ? window.surfsense?.models : undefined
  const settings = useElsewhereSettings()
  const [picking, setPicking] = useState<PickKind | null>(null)

  const pick = async (kind: PickKind) => {
    if (!bridge || picking) return
    setPicking(kind)
    try {
      const path = await bridge.pick(kind)
      if (path === null) return
      if (kind === "file") onOffered((await offerFile(path)).row)
      else await settings.addFolder.mutateAsync(path)
    } catch (error) {
      errorToast(
        kind === "file"
          ? intl.formatMessage({
              id: "models_elsewhere_pick_file_error",
              defaultMessage: "Can’t use this file",
            })
          : intl.formatMessage({
              id: "models_elsewhere_pick_folder_error",
              defaultMessage: "Can’t look in this folder",
            }),
        { description: refusal(error) }
      )
    } finally {
      setPicking(null)
    }
  }

  return { available: bridge !== undefined, picking, pick }
}

function refusal(error: unknown): string {
  if (error instanceof ApiError && error.code) {
    return unusableReason(error.code, error.message)
  }
  return error instanceof Error ? error.message : String(error)
}
