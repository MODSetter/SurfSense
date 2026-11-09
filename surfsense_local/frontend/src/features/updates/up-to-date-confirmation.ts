import { useCallback, useSyncExternalStore } from "react"

import { updatesBridge } from "./use-update-state"

type Updates = NonNullable<ReturnType<typeof updatesBridge>>

// Long enough to read two words, short enough that the pill is back for the next click.
export const UP_TO_DATE_SHOWN_MS = 2500

type Confirmation = {
  shown: boolean
  timer: number | undefined
  listeners: Set<() => void>
}

// One per updater, so the menu's check and the title bar's share it.
const confirmations = new WeakMap<Updates, Confirmation>()

function confirmationFor(updates: Updates) {
  let confirmation = confirmations.get(updates)
  if (!confirmation) {
    confirmation = { shown: false, timer: undefined, listeners: new Set() }
    confirmations.set(updates, confirmation)
  }
  return confirmation
}

function show(confirmation: Confirmation, shown: boolean) {
  confirmation.shown = shown
  for (const listener of confirmation.listeners) listener()
}

/** A check the user asked for found nothing newer: the title bar says so briefly. */
export function confirmUpToDate(updates: Updates) {
  const confirmation = confirmationFor(updates)
  window.clearTimeout(confirmation.timer)
  confirmation.timer = window.setTimeout(
    () => show(confirmation, false),
    UP_TO_DATE_SHOWN_MS
  )
  show(confirmation, true)
}

export function useUpToDateConfirmed(): boolean {
  const updates = updatesBridge()
  const subscribe = useCallback(
    (listener: () => void) => {
      if (!updates) return () => {}
      const { listeners } = confirmationFor(updates)
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    [updates]
  )
  return useSyncExternalStore(subscribe, () =>
    updates ? confirmationFor(updates).shown : false
  )
}
