import { useSyncExternalStore } from "react"

import type { MoveProgress } from "./storage-types"

// Outside the dialog: an app dialog remounts whenever what it opens over changes.
let current: MoveProgress | null = null
const listeners = new Set<() => void>()

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => void listeners.delete(listener)
}

export function useMoveProgress(): MoveProgress | null {
  return useSyncExternalStore(subscribe, () => current)
}

/** From startup: a move stops the API under the page, which must cover itself first. */
export function followMoveProgress(): () => void {
  const stop = window.surfsense?.storage?.onProgress((progress) => {
    current = progress
    listeners.forEach((listener) => listener())
  })
  return () => {
    stop?.()
    current = null
    listeners.forEach((listener) => listener())
  }
}
