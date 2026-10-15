import { useCallback, useState } from "react"

import type { WorkspaceDocument } from "../api"
import { advancePace, type TranscriptionPace } from "./pace"

const NONE: ReadonlyMap<number, TranscriptionPace> = new Map()

/**
 * The speed of each running transcription, timed by the windows its events
 * report. A re-read list carries no time, so it only ends the paces of
 * recordings no longer running: a run resumed after yielding starts afresh.
 */
export function useTranscriptionPaces() {
  const [paces, setPaces] = useState(NONE)

  const heard = useCallback((ids: number[], done_s: number) => {
    const at = Date.now()
    setPaces((current) => {
      const next = new Map(current)
      for (const id of ids) {
        next.set(id, advancePace(current.get(id), done_s, at))
      }
      return next
    })
  }, [])

  const keepRunning = useCallback((documents: WorkspaceDocument[]) => {
    setPaces((current) => {
      if (current.size === 0) return current
      const running = new Set(
        documents
          .filter((document) => document.status === "processing")
          .map((document) => document.id)
      )
      const next = new Map([...current].filter(([id]) => running.has(id)))
      return next.size === current.size ? current : next
    })
  }, [])

  return { paces, heard, keepRunning }
}
