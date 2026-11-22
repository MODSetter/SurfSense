import { useEffect, useSyncExternalStore } from "react"

import { onRunFrame } from "../runs/run-store"

/** The plan answers past its limit, billed as extra usage, until `resetsAt`. */
export type ExtraUsage = { resetsAt: Date | null }

// The plan's, not a thread's: the last reply anywhere says where it stands.
let current: ExtraUsage | null = null
let resetTimer: ReturnType<typeof setTimeout> | null = null
const listeners = new Set<() => void>()

function set(next: ExtraUsage | null) {
  current = next
  for (const listener of listeners) listener()
}

/** What a reply's `plan-extra-usage` frame says. */
export function notePlanUsage({
  using,
  resets_at,
}: {
  using: boolean
  resets_at: number | null
}) {
  if (resetTimer !== null) clearTimeout(resetTimer)
  resetTimer = null
  if (!using) {
    set(null)
    return
  }
  const resetsAt = resets_at === null ? null : new Date(resets_at * 1000)
  if (resetsAt !== null) {
    const left = resetsAt.getTime() - Date.now()
    if (left <= 0) {
      set(null)
      return
    }
    resetTimer = setTimeout(() => set(null), left)
  }
  set({ resetsAt })
}

export function extraUsage(): ExtraUsage | null {
  return current
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** Whether the plan is on extra usage now, from every run's frames. */
export function useExtraUsage(): ExtraUsage | null {
  useEffect(
    () =>
      onRunFrame((_threadId, event) => {
        if (event.type === "plan-extra-usage") notePlanUsage(event)
      }),
    []
  )
  return useSyncExternalStore(subscribe, extraUsage)
}
