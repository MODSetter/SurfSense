import { useEffect, useEffectEvent } from "react"

import { followWorkspaceEvents } from "@/features/workspaces/api"

const FIRST_RETRY_MS = 1_000
const LAST_RETRY_MS = 10_000

function wait(milliseconds: number, signal: AbortSignal) {
  return new Promise<void>((resolve) => {
    const timeout = window.setTimeout(resolve, milliseconds)
    signal.addEventListener(
      "abort",
      () => {
        window.clearTimeout(timeout)
        resolve()
      },
      { once: true }
    )
  })
}

/**
 * Calls `onChange` when the workspace's documents change by another hand: a
 * plugin, a second window, the worker. Also after a dropped stream is back,
 * for whatever changed while nothing was listening.
 */
export function useDocumentChanges(workspaceId: number, onChange: () => void) {
  const changed = useEffectEvent(onChange)

  useEffect(() => {
    const controller = new AbortController()
    const { signal } = controller

    void (async () => {
      let retry = FIRST_RETRY_MS
      let listenedBefore = false
      while (!signal.aborted) {
        try {
          for await (const event of followWorkspaceEvents(
            workspaceId,
            signal
          )) {
            if (event.type === "connected") {
              retry = FIRST_RETRY_MS
              // The first connection needs no reload: mounting just loaded the list.
              if (listenedBefore) changed()
              listenedBefore = true
            } else if (event.type === "documents") {
              changed()
            }
          }
        } catch {
          // Dropped or refused: the list still works, and the loop tries again.
        }
        await wait(retry, signal)
        retry = Math.min(retry * 2, LAST_RETRY_MS)
      }
    })()

    return () => controller.abort()
  }, [workspaceId])
}
