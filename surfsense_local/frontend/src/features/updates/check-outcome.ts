import { useCallback, useSyncExternalStore } from "react"

import { updatesBridge } from "./use-update-state"

type Updates = NonNullable<ReturnType<typeof updatesBridge>>

export type CheckOutcome = "up-to-date" | "failed"

// Long enough to read two words, short enough that the pill is back for the next click.
export const CHECK_OUTCOME_SHOWN_MS = 2500

type Shown = {
  outcome: CheckOutcome | null
  timer: number | undefined
  listeners: Set<() => void>
}

// One per updater, so the menu's check and the title bar's share it.
const shownByUpdater = new WeakMap<Updates, Shown>()

function shownFor(updates: Updates) {
  let shown = shownByUpdater.get(updates)
  if (!shown) {
    shown = { outcome: null, timer: undefined, listeners: new Set() }
    shownByUpdater.set(updates, shown)
  }
  return shown
}

function show(shown: Shown, outcome: CheckOutcome | null) {
  shown.outcome = outcome
  for (const listener of shown.listeners) listener()
}

/** How a check the user asked for ended; the title bar says so briefly. */
export function showCheckOutcome(updates: Updates, outcome: CheckOutcome) {
  const shown = shownFor(updates)
  window.clearTimeout(shown.timer)
  shown.timer = window.setTimeout(
    () => show(shown, null),
    CHECK_OUTCOME_SHOWN_MS
  )
  show(shown, outcome)
}

export function useCheckOutcome(): CheckOutcome | null {
  const updates = updatesBridge()
  const subscribe = useCallback(
    (listener: () => void) => {
      if (!updates) return () => {}
      const { listeners } = shownFor(updates)
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    [updates]
  )
  return useSyncExternalStore(subscribe, () =>
    updates ? shownFor(updates).outcome : null
  )
}
