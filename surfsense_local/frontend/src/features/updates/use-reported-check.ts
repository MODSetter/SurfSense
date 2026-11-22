import { useEffect } from "react"

import type { UpdateState } from "@/lib/api"

import { showCheckOutcome } from "./check-outcome"
import { useCheckForUpdates } from "./use-check-for-updates"
import { updatesBridge } from "./use-update-state"

type Updates = NonNullable<ReturnType<typeof updatesBridge>>

type Reporting = {
  // A result counts only once this check is seen running, so an earlier
  // check's "up to date" never answers it.
  phase: "none" | "requested" | "running"
  // Until the first click's consent is answered, so a second click never asks again.
  asking: boolean
}

// One per updater, not per surface: the menu and the title bar share a check,
// so its one result is reported once.
const reporting = new WeakMap<Updates, Reporting>()

function reportingFor(updates: Updates) {
  let shared = reporting.get(updates)
  if (!shared) {
    shared = { phase: "none", asking: false }
    reporting.set(updates, shared)
  }
  return shared
}

/**
 * A check from the app menu or the title bar, where Settings may be closed.
 * Its outcome, up to date, failed or an update found, shows in the title bar.
 */
export function useReportedCheck() {
  const check = useCheckForUpdates()

  // Every state main sends, not the rendered one: a render can batch away "checking".
  useEffect(() => {
    const updates = updatesBridge()
    if (!updates) return
    const shared = reportingFor(updates)
    return updates.onState((state: UpdateState) => {
      if (state.status === "checking") {
        if (shared.phase === "requested") shared.phase = "running"
        return
      }
      if (shared.phase !== "running") return
      shared.phase = "none"
      if (state.status === "up-to-date") showCheckOutcome(updates, "up-to-date")
      else if (state.status === "error") showCheckOutcome(updates, "failed")
    })
  }, [])

  return async () => {
    const updates = updatesBridge()
    if (!updates) return
    const shared = reportingFor(updates)
    if (shared.asking) return
    shared.asking = true
    try {
      shared.phase = "requested"
      const started = await check()
      if (!started && shared.phase === "requested") shared.phase = "none"
    } finally {
      shared.asking = false
    }
  }
}
