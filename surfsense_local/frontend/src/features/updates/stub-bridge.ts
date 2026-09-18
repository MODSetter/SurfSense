import { vi } from "vitest"

import type { UpdateState } from "@/lib/api"

/**
 * Stands in for the preload bridge, so a test can drive update state the way
 * the main process would. Shared by every surface that reads it.
 */
export function stubUpdateBridge(initial: {
  automatic: boolean
  state: UpdateState
}) {
  let prefs = { automatic: initial.automatic }
  let state = initial.state
  const listeners = new Set<(state: UpdateState) => void>()
  const calls: string[] = []
  window.surfsense = {
    apiUrl: "",
    platform: "darwin",
    openDocument: vi.fn(),
    revealDocument: vi.fn(),
    updates: {
      prefs: async () => prefs,
      setAutomatic: async (automatic: boolean) => {
        calls.push(`automatic:${automatic}`)
        prefs = { automatic }
        return prefs
      },
      state: async () => state,
      check: async () => {
        calls.push("check")
      },
      install: async () => {
        calls.push("install")
      },
      onState: (listener) => {
        listeners.add(listener)
        return () => listeners.delete(listener)
      },
    },
  }
  return {
    calls,
    push(next: UpdateState) {
      state = next
      for (const listener of listeners) listener(next)
    },
  }
}
